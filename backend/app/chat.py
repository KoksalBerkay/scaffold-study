"""Tutor chat: Tutor ⇄ Reviewer loop, attachments, tools, and background agents
(Note-taker, Memory updater, Chat summary)."""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from . import llm, materials
from .config import WORKSPACE, get_memory, load_settings, materials_dir, memory_path, notes_dir, render_prompt
from .files import normalize_math, notes_tree, note_target, parse_file_blocks, write_note
from .planner import PLAN_DIR, plan_file, today_str, with_heartbeat

router = APIRouter()

CHATS = WORKSPACE / "chats"
UPLOADS = WORKSPACE / "uploads"
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
COMPACT_CHARS = 40_000
KEEP_TURNS = 6

# ---------------- event bus (background toasts) ----------------
_subscribers: set[asyncio.Queue] = set()


def broadcast(ev: dict):
    for q in list(_subscribers):
        q.put_nowait(ev)


@router.get("/api/events")
async def events():
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.add(q)

    async def gen():
        try:
            yield "data: {\"type\": \"hello\"}\n\n"
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=20)
                    yield f"data: {json.dumps(ev)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            _subscribers.discard(q)
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


# ---------------- storage ----------------

def chat_dir(cid: str) -> Path:
    if not re.fullmatch(r"[a-z0-9]{6,32}", cid):
        raise HTTPException(400, "Bad chat id")
    return CHATS / cid


def load_meta(cid: str) -> dict:
    p = chat_dir(cid) / "meta.json"
    if not p.exists():
        raise HTTPException(404, "Chat not found")
    return json.loads(p.read_text())


def save_meta(meta: dict, create: bool = False):
    d = chat_dir(meta["id"])
    if not create and not d.exists():
        raise ChatGone()
    d.mkdir(parents=True, exist_ok=True)
    meta["updated"] = time.time()
    (d / "meta.json").write_text(json.dumps(meta, indent=2))


def load_messages(cid: str) -> list[dict]:
    p = chat_dir(cid) / "transcript.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


class ChatGone(Exception):
    pass


def append_message(cid: str, msg: dict):
    d = chat_dir(cid)
    if not d.exists():
        raise ChatGone()  # the chat was deleted while the tutor was answering
    with open(d / "transcript.jsonl", "a") as f:
        f.write(json.dumps(msg) + "\n")


def read_summary(cid: str) -> str:
    p = chat_dir(cid) / "summary.md"
    return p.read_text() if p.exists() else ""


FOLDERS_FILE = CHATS / "folders.json"
TEST_FOLDER = "Reviewer tests"


def load_folders() -> list[dict]:
    if FOLDERS_FILE.exists():
        try:
            return json.loads(FOLDERS_FILE.read_text())
        except Exception:
            return []
    return []


def save_folders(folders: list[dict]):
    CHATS.mkdir(parents=True, exist_ok=True)
    FOLDERS_FILE.write_text(json.dumps(folders, indent=2))


def ensure_folder(name: str) -> str:
    folders = load_folders()
    for f in folders:
        if f["name"] == name:
            return f["id"]
    f = {"id": uuid.uuid4().hex[:10], "name": name, "created": time.time()}
    save_folders(folders + [f])
    return f["id"]


def _harness_title(meta: dict) -> str:
    m = re.match(r"\[harness\] (\S+) review=(True|False)", meta.get("title") or "")
    if not m:
        return meta.get("title") or "Test"
    nice = {"eigenvalues": "Eigenvalues", "sql-grouping": "SQL grouping", "gauss-sphere": "Gauss's law"}.get(m[1], m[1])
    return f"{nice} · Reviewer {'on' if m[2] == 'True' else 'off'}"


@router.get("/api/chats")
def list_chats():
    out = []
    if CHATS.exists():
        for d in CHATS.iterdir():
            m = d / "meta.json"
            if not m.exists():
                continue
            meta = json.loads(m.read_text())
            if meta.get("harness") and not meta.get("folder"):
                # show test conversations in their own folder, with readable titles
                meta["folder"] = ensure_folder(TEST_FOLDER)
                meta["title"] = _harness_title(meta)
                (d / "meta.json").write_text(json.dumps(meta, indent=2))
            out.append({k: meta.get(k) for k in ("id", "title", "updated", "created", "task", "folder", "harness", "badge")})
    return sorted(out, key=lambda x: -(x["updated"] or 0))


@router.get("/api/chat-folders")
def get_folders():
    return load_folders()


@router.post("/api/chat-folders")
def create_folder(body: dict = Body(...)):
    name = (body.get("name") or "").strip() or "New folder"
    f = {"id": uuid.uuid4().hex[:10], "name": name[:60], "created": time.time()}
    save_folders(load_folders() + [f])
    return f


@router.patch("/api/chat-folders/{fid}")
def rename_folder(fid: str, body: dict = Body(...)):
    folders = load_folders()
    for f in folders:
        if f["id"] == fid:
            if "name" in body:
                f["name"] = (body["name"] or "").strip()[:60] or f["name"]
            if "collapsed" in body:
                f["collapsed"] = bool(body["collapsed"])
    save_folders(folders)
    return folders


@router.delete("/api/chat-folders/{fid}")
def delete_folder(fid: str):
    """Delete a folder; its chats move back to the top level (never deleted)."""
    save_folders([f for f in load_folders() if f["id"] != fid])
    if CHATS.exists():
        for d in CHATS.iterdir():
            m = d / "meta.json"
            if m.exists():
                meta = json.loads(m.read_text())
                if meta.get("folder") == fid:
                    meta["folder"] = None
                    m.write_text(json.dumps(meta, indent=2))
    return {"ok": True}


@router.post("/api/chats")
def create_chat(body: dict = Body(default={})):
    cid = uuid.uuid4().hex[:12]
    meta = {"id": cid, "title": body.get("title") or "", "created": time.time(), "task": body.get("task"),
            "pinned_files": body.get("pinned_files") or [], "notes_touched": [], "harness": bool(body.get("harness")),
            "badge": body.get("badge"),
            "folder": body.get("folder") if body.get("folder") in {f["id"] for f in load_folders()} else None}
    save_meta(meta, create=True)
    return meta


@router.get("/api/chats/{cid}")
def get_chat(cid: str):
    return {"meta": load_meta(cid), "messages": load_messages(cid), "summary": read_summary(cid)}


@router.patch("/api/chats/{cid}")
def rename_chat(cid: str, body: dict = Body(...)):
    meta = load_meta(cid)
    if "title" in body:
        meta["title"] = (body.get("title") or "").strip()[:120] or meta["title"]
    if "folder" in body:
        fid = body.get("folder")
        meta["folder"] = fid if fid in {f["id"] for f in load_folders()} else None
    p = chat_dir(cid) / "meta.json"
    p.write_text(json.dumps(meta, indent=2))  # moving/renaming must not reorder by "updated"
    return meta


@router.delete("/api/chats/{cid}")
def delete_chat(cid: str):
    d = chat_dir(cid)
    if d.exists():
        shutil.rmtree(d)
    return {"ok": True}


# ---------------- uploads ----------------

def _upload_record(uid: str, name: str, path: Path) -> dict:
    ext = path.suffix.lower()
    kind = "image" if ext in IMAGE_EXT else ("pdf" if ext == ".pdf" else "text")
    return {"id": uid, "name": name, "kind": kind, "url": f"/api/uploads/{uid}"}


@router.post("/api/uploads")
async def upload(file: UploadFile = File(...)):
    UPLOADS.mkdir(parents=True, exist_ok=True)
    name = file.filename or "pasted.png"
    ext = Path(name).suffix.lower() or ".png"
    uid = uuid.uuid4().hex[:16]
    p = UPLOADS / f"{uid}{ext}"
    p.write_bytes(await file.read())
    (UPLOADS / f"{uid}.json").write_text(json.dumps({"name": name, "file": p.name}))
    return _upload_record(uid, name, p)


def upload_path(uid: str) -> tuple[Path, str]:
    if not re.fullmatch(r"[a-f0-9]{16}", uid):
        raise HTTPException(400)
    meta = UPLOADS / f"{uid}.json"
    if not meta.exists():
        raise HTTPException(404)
    m = json.loads(meta.read_text())
    return UPLOADS / m["file"], m["name"]


@router.get("/api/uploads/{uid}")
def get_upload(uid: str):
    p, _ = upload_path(uid)
    return FileResponse(p)


@router.post("/api/materials/page")
def attach_material_page(body: dict = Body(...)):
    """Render a page of a material file as an image attachment."""
    root = materials_dir()
    if not root:
        raise HTTPException(400, "No materials folder")
    src = materials.safe_path(root, body["file"])
    page = int(body.get("page", 1))
    img = materials.render_page(src, page)
    UPLOADS.mkdir(parents=True, exist_ok=True)
    uid = uuid.uuid4().hex[:16]
    dst = UPLOADS / f"{uid}.png"
    shutil.copy(img, dst)
    name = f"{src.name} · p.{page}"
    (UPLOADS / f"{uid}.json").write_text(json.dumps({"name": name, "file": dst.name}))
    return _upload_record(uid, name, dst)


@router.get("/api/materials/list")
def materials_list():
    root = materials_dir()
    if not root:
        return {"root": None, "files": []}
    return {"root": str(root), "files": [
        {"rel": str(p.relative_to(root)), "pages": materials.page_count(p)} for p in materials.iter_files(root)]}


def expand_attachments(atts: list[dict]) -> tuple[str, list[str]]:
    """Returns extra text for the model and a list of image paths."""
    text_parts, images = [], []
    for a in atts or []:
        try:
            p, name = upload_path(a["id"])
        except HTTPException:
            continue
        ext = p.suffix.lower()
        if ext in IMAGE_EXT:
            images.append(str(p))
        elif ext == ".pdf":
            body = materials.read_pages(p, None, max_chars=15000)
            text_parts.append(f"[Attached PDF: {name}]\n{body}")
            for i in (1, 2):
                try:
                    images.append(str(materials.render_page(p, i)))
                except Exception:
                    break
        else:
            text_parts.append(f"[Attached file: {name}]\n{p.read_text(errors='replace')[:15000]}")
    return "\n\n".join(text_parts), images


# ---------------- context for the tutor ----------------

TOOL_RE = re.compile(r"<<TOOL\s+(\w+)\s*(\{.*?\})?\s*>>", re.S)

TOOL_PROTOCOL = """
## Tool calls
The context below is already loaded. If you need something that is not there, reply with ONLY tool lines, nothing else, for example:
<<TOOL read_material {"file": "Course/Exams/paper.pdf", "pages": "2-3"}>>
<<TOOL view_page {"file": "Course/Exams/paper.pdf", "page": 2}>>
Available tools:
- search_materials {"query": "..."}: find pages in the student's materials.
- read_material {"file": "<path relative to the materials folder>", "pages": "1-3"}: page text.
- view_page {"file": "...", "page": n}: the page as an image (formulas, diagrams, tables, handwriting).
- read_note {"path": "<path in the notes folder>"}: an existing note.
- read_chat_summary {"id": "<chat id>"}: what happened in another chat.
You then get the results and write your reply. At most 2 tool rounds. Never mix tool lines with a reply to the student.
"""


def _materials_listing(root: Path | None, limit: int = 160) -> str:
    if not root:
        return "(no materials folder selected)"
    files = [str(p.relative_to(root)) for p in materials.iter_files(root)]
    out = "\n".join(f"- {f}" for f in files[:limit])
    if len(files) > limit:
        out += f"\n- … {len(files) - limit} more"
    return out or "(empty)"


def _rel(root: Path | None, link: str) -> str | None:
    if not root:
        return None
    try:
        return str(materials.safe_path(root, link).relative_to(root))
    except Exception:
        return None


def build_context(meta: dict, user_text: str) -> tuple[str, str]:
    """Returns (context for the tutor, material excerpt for the reviewer)."""
    root = materials_dir()
    parts = [f"Today is {today_str()}."]
    material_used = []

    if meta.get("task"):
        parts.append(f"## This chat was started from a study-plan task\n{meta['task']}")
    for link in meta.get("pinned_files") or []:
        rel = _rel(root, link)
        if rel:
            text = materials.read_pages(root / rel, None, max_chars=12000)
            block = f"## Pinned material: {rel}\n{text}"
            parts.append(block)
            material_used.append(block)

    if root and user_text.strip():
        hits = materials.search(root, user_text, k=4)
        if hits:
            block = "## Material pages that match the student's message\n" + "\n\n".join(
                f"[{h['file']} · page {h['page']}]\n{h['text'][:1200]}" for h in hits)
            parts.append(block)
            material_used.append(block)

    qp = plan_file("Quick Plan")
    if qp.exists():
        parts.append("## The student's Quick Plan (this week)\n" + qp.read_text()[:3500])

    parts.append("## Materials folder\n" + _materials_listing(root))

    tree = [n["path"] for n in notes_tree() if not n["path"].startswith(PLAN_DIR + "/")]
    parts.append("## Existing notes\n" + ("\n".join(f"- {t}" for t in tree[:120]) or "(none yet)"))
    for t in (meta.get("notes_touched") or [])[-2:]:
        try:
            parts.append(f"## Note from this chat: {t}\n" + note_target(t).read_text()[:6000])
        except Exception:
            pass

    others = []
    for c in list_chats()[:12]:
        if c["id"] == meta["id"] or c.get("harness"):
            continue
        s = read_summary(c["id"])
        others.append(f"- {c['id']}: {c['title'] or 'untitled'}" + (f" (summary: {' '.join(s.split())[:200]}…)" if s else ""))
    if others:
        parts.append("## Other chats\n" + "\n".join(others))

    return "\n\n".join(parts), "\n\n".join(material_used)


async def run_tool(name: str, args: dict) -> tuple[str, list[str]]:
    root = materials_dir()
    try:
        if name == "search_materials":
            hits = materials.search(root, args.get("query", ""), k=5) if root else []
            return "\n\n".join(f"[{h['file']} · page {h['page']}]\n{h['text'][:1200]}" for h in hits) or "No matches.", []
        if name == "read_material":
            p = materials.safe_path(root, args["file"])
            return materials.read_pages(p, args.get("pages")) or "(no text on those pages; try view_page)", []
        if name == "view_page":
            p = materials.safe_path(root, args["file"])
            img = materials.render_page(p, int(args.get("page", 1)))
            return f"(page {args.get('page', 1)} of {args['file']} attached as an image)", [str(img)]
        if name == "read_note":
            return note_target(args["path"]).read_text()[:12000], []
        if name == "read_chat_summary":
            return read_summary(args["id"]) or "(no summary yet)", []
    except Exception as e:
        return f"Tool error: {e}", []
    return f"Unknown tool {name}", []


def history_for_model(cid: str, messages: list[dict]) -> list[dict]:
    """Compaction: if the chat is long, the summary replaces older turns."""
    total = sum(len(m["content"]) for m in messages)
    summary = read_summary(cid)
    msgs = messages
    prefix = []
    if total > COMPACT_CHARS and summary:
        msgs = messages[-KEEP_TURNS * 2:]
        prefix = [{"role": "user", "content": f"(Summary of the earlier part of this chat)\n{summary}"},
                  {"role": "assistant", "content": "Understood. Continuing from there."}]
    out = []
    n_user = sum(1 for m in msgs if m["role"] == "user")
    seen_user = 0
    for m in msgs:
        item = {"role": m["role"], "content": m.get("model_content") or m["content"]}
        if m["role"] == "user":
            seen_user += 1
            if seen_user > n_user - 2:  # only the last two user turns keep their images
                item["images"] = m.get("image_paths") or []
        out.append(item)
    return prefix + out


def parse_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


# ---------------- the main loop ----------------

async def tutor_turn(cid: str, body: dict, review: bool | None = None, background_jobs: bool = True):
    meta = load_meta(cid)
    settings = load_settings()
    if review is not None:
        settings["review"] = review
    text = (body.get("text") or "").strip()
    atts = body.get("attachments") or []
    extra_text, images = expand_attachments(atts)

    user_msg = {"role": "user", "content": text, "attachments": atts, "ts": time.time(),
                "image_paths": images, "model_content": (text + ("\n\n" + extra_text if extra_text else "")) or "(see the attached images)"}
    prior = load_messages(cid)
    append_message(cid, user_msg)
    if not meta.get("title"):
        meta["title"] = (text or (atts[0]["name"] if atts else "New chat"))[:70]
        save_meta(meta)
        broadcast({"type": "chats"})
    yield {"type": "user_saved"}

    yield {"type": "status", "stage": "context", "detail": "Reading your materials, notes and plan"}
    context, material_used = await asyncio.to_thread(build_context, meta, text)
    system = render_prompt("tutor") + "\n" + TOOL_PROTOCOL + "\n# Context\n" + context
    convo = history_for_model(cid, prior + [user_msg])

    # ---- draft, with up to 2 tool rounds
    draft = None
    tool_log = []
    for round_ in range(3):
        out = None
        async for ev in with_heartbeat(llm.complete("tutor", system, convo), "drafting",
                                       "The tutor is writing" if round_ == 0 else "The tutor is reading what it looked up"):
            if isinstance(ev, tuple):
                out = ev[1]
            else:
                yield ev
        calls = TOOL_RE.findall(out)
        if not calls or round_ == 2:
            draft = TOOL_RE.sub("", out).strip() if calls else out
            break
        results, imgs = [], []
        for name, raw in calls[:4]:
            try:
                args = json.loads(raw) if raw else {}
            except Exception:
                args = {}
            label = args.get("file") or args.get("query") or args.get("path") or args.get("id") or ""
            yield {"type": "status", "stage": "tool", "detail": f"{name.replace('_', ' ')}: {label}"}
            res, im = await run_tool(name, args)
            results.append(f"### {name} {json.dumps(args)}\n{res}")
            imgs += im
            tool_log.append({"tool": name, "args": args})
        material_used += "\n\n" + "\n\n".join(results)
        convo = convo + [{"role": "assistant", "content": out},
                         {"role": "user", "content": "TOOL RESULTS:\n" + "\n\n".join(results), "images": imgs}]

    # ---- review loop
    review = {"enabled": bool(settings.get("review")), "rounds": [], "student_note": ""}
    if settings.get("review"):
        recent = "\n\n".join(f"{'STUDENT' if m['role'] == 'user' else 'TUTOR'}: {m['content'][:1500]}" for m in prior[-6:])
        rsys = render_prompt("reviewer")
        for r in range(int(settings.get("max_review_rounds", 2)) + 1):
            yield {"type": "status", "stage": "reviewing", "detail": "Checking correctness, completeness and that it doesn't give the answer away"}
            rin = (f"STUDENT'S LATEST MESSAGE:\n{user_msg['model_content']}\n\nRECENT CONVERSATION:\n{recent or '(start of chat)'}"
                   f"\n\nMATERIAL THE TUTOR USED:\n{material_used[:14000] or '(none)'}\n\nTUTOR'S DRAFT:\n{draft}")
            verdict = None
            async for ev in with_heartbeat(llm.complete("reviewer", rsys, [{"role": "user", "content": rin, "images": images}]),
                                           "reviewing", "Checking correctness, completeness and that it doesn't give the answer away"):
                if isinstance(ev, tuple):
                    verdict = parse_json(ev[1]) or {"verdict": "approve", "issues": [], "student_note": ""}
                else:
                    yield ev
            issues = verdict.get("issues") or []
            review["rounds"].append({"verdict": verdict.get("verdict"), "issues": issues})
            if verdict.get("student_note"):
                review["student_note"] = verdict["student_note"]
            yield {"type": "review", "round": r + 1, "verdict": verdict.get("verdict"), "issues": issues}
            if verdict.get("verdict") != "revise" or not issues or r == int(settings.get("max_review_rounds", 2)):
                break
            fb = "\n".join(f"- [{i.get('type')}] {i.get('where', '')}: {i.get('fix', '')}" for i in issues)
            convo2 = convo + [{"role": "assistant", "content": draft},
                              {"role": "user", "content": "REVIEWER FEEDBACK. Fix every point and return the full revised message for the student, nothing else. Keep all correct teaching from your draft; change only what the points require. Never reveal a result the student has not produced yet:\n" + fb}]
            async for ev in with_heartbeat(llm.complete("tutor", system, convo2), "revising", f"Fixing {len(issues)} issue{'s' if len(issues) != 1 else ''} the reviewer found"):
                if isinstance(ev, tuple):
                    draft = TOOL_RE.sub("", ev[1]).strip()
                else:
                    yield ev
        last = review["rounds"][-1]["verdict"] if review["rounds"] else "approve"
        review["final"] = "approved" if last != "revise" else "best_effort"

    final = normalize_math(draft)
    asst = {"role": "assistant", "content": final, "ts": time.time(), "review": review, "tools": tool_log}
    append_message(cid, asst)
    save_meta(meta)
    yield {"type": "message", "message": asst}

    if background_jobs:
        asyncio.create_task(background(cid, user_msg, asst))


# ---------------- background agents ----------------
_note_locks: dict[str, asyncio.Lock] = {}


async def background(cid: str, user_msg: dict, asst: dict):
    settings = load_settings()
    jobs = [memory_job(cid, user_msg, asst, prev_tutor(cid)), summary_job(cid)]
    if settings.get("auto_notes"):
        jobs.append(notes_job(cid, user_msg, asst))
    await asyncio.gather(*jobs, return_exceptions=True)


def prev_tutor(cid: str) -> str:
    msgs = load_messages(cid)
    tutors = [m for m in msgs if m["role"] == "assistant"]
    return tutors[-2]["content"] if len(tutors) >= 2 else ""


async def notes_job(cid: str, user_msg: dict, asst: dict):
    lock = _note_locks.setdefault(cid, asyncio.Lock())
    async with lock:
        try:
            meta = load_meta(cid)
            tree = [n["path"] for n in notes_tree() if not n["path"].startswith(PLAN_DIR + "/")]
            candidates = list(dict.fromkeys(meta.get("notes_touched") or []))[-3:]
            existing = "\n\n".join(f"<<<FILE notes/{p}\n{note_target(p).read_text()}\nFILE>>>"
                                   for p in candidates if note_target(p).exists())
            root = materials_dir()
            pinned = [_rel(root, l) for l in meta.get("pinned_files") or []]
            user = (f"LATEST EXCHANGE:\nSTUDENT: {user_msg['model_content'][:6000]}\n\nTUTOR: {asst['content']}"
                    + (f"\n\nSOURCE MATERIAL FOR THIS CHAT: {', '.join(p for p in pinned if p)}" if any(pinned) else "")
                    + (f"\n\nCHAT TASK: {meta['task']}" if meta.get("task") else "")
                    + "\n\nNOTES FOLDER TREE:\n" + ("\n".join(f"- notes/{t}" for t in tree) or "(empty)")
                    + "\n\nNOTES YOU MAY UPDATE (current content):\n" + (existing or "(none yet; create new ones)"))
            out = await llm.complete("background", render_prompt("notetaker"),
                                     [{"role": "user", "content": user, "images": user_msg.get("image_paths") or []}])
            written = []
            for path, content in parse_file_blocks(out):
                rel = path[len("notes/"):] if path.startswith("notes/") else path
                if rel.startswith(PLAN_DIR + "/"):
                    continue
                write_note(rel, content)
                written.append(rel if rel.endswith(".md") else rel + ".md")
            if written:
                meta = load_meta(cid)
                meta["notes_touched"] = list(dict.fromkeys((meta.get("notes_touched") or []) + written))
                save_meta(meta)
                broadcast({"type": "notes", "paths": written, "chat": cid})
        except Exception as e:
            broadcast({"type": "bg_error", "title": "Note-taker failed", "message": str(e)[:200]})


async def memory_job(cid: str, user_msg: dict, asst: dict, prev: str):
    try:
        if not prev:
            return  # criticism refers to an earlier tutor message
        user = (f"CURRENT MEMORY FILE:\n{get_memory()}\n\nLATEST EXCHANGE:\nTUTOR (previous message): {prev[:5000]}"
                f"\n\nSTUDENT'S REPLY: {user_msg['content'][:3000]}")
        out = await llm.complete("background", render_prompt("memory_updater"), [{"role": "user", "content": user}])
        data = parse_json(out)
        if data and data.get("changed") and data.get("memory"):
            mem = data["memory"]
            if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", mem):
                return  # backslash trap: refuse corrupted text
            memory_path().write_text(mem.strip() + "\n")
            broadcast({"type": "memory", "summary": data.get("change_summary") or "Memory updated", "chat": cid})
    except Exception as e:
        broadcast({"type": "bg_error", "title": "Memory update failed", "message": str(e)[:200]})


async def summary_job(cid: str):
    try:
        msgs = load_messages(cid)
        if sum(len(m["content"]) for m in msgs) < 6000:
            return
        prev = read_summary(cid)
        recent = "\n\n".join(f"{'STUDENT' if m['role'] == 'user' else 'TUTOR'}: {m['content']}" for m in msgs[-8:])
        user = f"PREVIOUS SUMMARY:\n{prev or '(empty)'}\n\nMESSAGES SINCE THEN:\n{recent[:30000]}"
        out = await llm.complete("background", render_prompt("summary"), [{"role": "user", "content": user}])
        (chat_dir(cid) / "summary.md").write_text(normalize_math(out))
    except Exception:
        pass


@router.post("/api/chats/{cid}/messages")
async def send_message(cid: str, body: dict = Body(...)):
    load_meta(cid)
    if not (body.get("text") or "").strip() and not body.get("attachments"):
        raise HTTPException(400, "Write a message or attach something first.")

    async def stream():
        try:
            async for ev in tutor_turn(cid, body):
                yield f"data: {json.dumps(ev)}\n\n"
        except llm.LLMError as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        except ChatGone:
            yield f"data: {json.dumps({'type': 'error', 'message': 'This chat was deleted.'})}\n\n"
        except Exception as e:  # noqa
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': f'{type(e).__name__}: {e}'})}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
