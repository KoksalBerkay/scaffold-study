"""The Notes agent: one long-running conversation per course that keeps that course's notes.

After every reviewed tutor answer it records what was taught (section-level edits, so long notes are never
rewritten from scratch). A Notes reviewer checks each change before it is saved. Under the answer the student
sees a card with what changed, and can reply to it ("no, put the derivation first"); the agent fixes the note
and saves lasting preferences as rules in the course's memory.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from pathlib import Path

from fastapi import Body, HTTPException

from . import llm
from .chat import (TOOL_RE, ChatGone, broadcast, chat_course, chat_dir, load_meta, parse_json, read_summary, router,
                   save_meta)
from .config import (WORKSPACE, course_memory_path, course_slug, get_course_memory, load_settings, read_json,
                     render_prompt, write_atomic)
from .files import normalize_math, note_target, notes_tree, write_note
from .planner import plan_dir

GENERAL = "General"
HISTORY_KEEP = 10            # messages of the agent's own conversation sent each time (the rest is summarized)
MAX_FILE_CHARS = 12_000      # notes up to this size are given in full; longer ones as outline + relevant sections
SECTION_BUDGET = 10_000      # characters of relevant sections given from a long note
SECTION_RE = re.compile(r"<<<SECTION\s+(.+?)\s*\n(.*?)(?:\nSECTION>>>|(?=\n<<<(?:SECTION|FILE|RULE))|\Z)", re.S)
FILE_RE = re.compile(r"<<<FILE\s+(.+?)\s*\n(.*?)(?:\nFILE>>>|(?=\n<<<(?:SECTION|FILE|RULE))|\Z)", re.S)
RULE_RE = re.compile(r"<<<RULE\s+(.*?)\s*RULE>>>", re.S)
RENAME_RE = re.compile(r"<<<RENAME\s+(.+?)\s*->\s*(.+?)\s*RENAME>>>", re.S)
SUMMARY_RE = re.compile(r"^SUMMARY:\s*(.+)$", re.M)
_locks: dict[str, asyncio.Lock] = {}


# ---------------- where a course's notes live ----------------

def course_of(meta: dict) -> str:
    return chat_course(meta) or GENERAL


def course_folder(course: str) -> str:
    """The course's folder inside the notes folder: the one set on the chat folder, else a folder with the
    course's name (an existing one is reused, compared case-insensitively)."""
    from .chat import load_folders
    for f in load_folders():
        if f["name"] == course and f.get("notes_folder"):
            return f["notes_folder"].strip("/")
    if course == GENERAL:
        return ""
    from .config import notes_dir
    nd = notes_dir()
    for d in nd.iterdir() if nd.exists() else []:
        if d.is_dir() and d.name.lower() == course.lower():
            return d.name
    return course


def _rel(path: str) -> str:
    path = path.strip().strip("`")
    return path[len("notes/"):] if path.startswith("notes/") else path


def _folder_files(folder: str) -> list[str]:
    pd = plan_dir() + "/"
    return [n["path"] for n in notes_tree()
            if (not folder or n["path"].startswith(folder.rstrip("/") + "/")) and not n["path"].startswith(pd)]


# ---------------- the agent's own conversation ----------------

def _hist_path(course: str) -> Path:
    return WORKSPACE / "notes_agents" / f"{course_slug(course)}.jsonl"


def _load_history(course: str) -> list[dict]:
    p = _hist_path(course)
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def _append_history(course: str, *msgs: dict):
    p = _hist_path(course)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as f:
        for m in msgs:
            f.write(json.dumps({**m, "ts": time.time()}) + "\n")


def _condense(message: str) -> str:
    """Student feedback is kept in full (it is what the agent must remember); lessons are kept short."""
    if message.startswith(("STUDENT FEEDBACK", "STUDENT REQUEST", "NOTES REVIEWER", "NOT SAVED")):
        return message[:2000]
    return message[:900] + (" …" if len(message) > 900 else "")


def _summary_path(course: str) -> Path:
    return WORKSPACE / "notes_agents" / f"{course_slug(course)}.summary.md"


def _history_for_model(course: str) -> list[dict]:
    hist = _load_history(course)
    keep = hist[-HISTORY_KEEP:]
    if keep and keep[0]["role"] == "assistant":
        keep = keep[1:]
    out = []
    sp = _summary_path(course)
    if len(hist) > len(keep) and sp.exists():
        out = [{"role": "user", "content": "(What happened earlier in this course's notes conversation)\n" + sp.read_text()},
               {"role": "assistant", "content": "SUMMARY: understood"}]
    return out + [{"role": m["role"], "content": m["content"]} for m in keep]


async def _refresh_summary(course: str):
    hist = _load_history(course)
    if len(hist) <= HISTORY_KEEP or len(hist) % 6:
        return
    sp = _summary_path(course)
    older = "\n\n".join(f"{m['role'].upper()}: {m['content'][:3000]}" for m in hist[:-HISTORY_KEEP][-24:])
    prompt = ("Summarize this notes agent's earlier work for one course in under 25 lines: which notes exist and what "
              "they cover, and every correction or preference the student gave about the notes (keep those word for word).")
    try:
        out = await llm.complete("notes", prompt, [{"role": "user", "content": f"PREVIOUS SUMMARY:\n{sp.read_text() if sp.exists() else '(none)'}\n\nOLDER MESSAGES:\n{older}"}])
        write_atomic(sp, out.strip() + "\n")
    except Exception:
        pass


# ---------------- applying edits ----------------

def _heading_level(line: str) -> int:
    m = re.match(r"^(#{1,6})\s", line)
    return len(m.group(1)) if m else 0


def apply_section(text: str, section: str) -> tuple[str, str, str]:
    """Replace the section that starts with the same heading line, or append it. Returns (new_text, old, action)."""
    section = section.strip("\n")
    head = section.split("\n", 1)[0].strip()
    level = _heading_level(head)
    lines = text.split("\n")
    in_code = False
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code = not in_code
        if not in_code and level and line.strip() == head:
            start = i
            break
    if start is None:
        new = text.rstrip("\n") + "\n\n" + section + "\n"
        return new, "", "added"
    end = len(lines)
    in_code = False
    for j in range(start + 1, len(lines)):
        if lines[j].strip().startswith("```"):
            in_code = not in_code
        if not in_code and 0 < _heading_level(lines[j]) <= level:
            end = j
            break
    old = "\n".join(lines[start:end]).strip("\n")
    new_lines = lines[:start] + section.split("\n") + ([""] if end < len(lines) else []) + lines[end:]
    return "\n".join(new_lines).rstrip("\n") + "\n", old, "updated"


def plan_changes(out: str, folder: str) -> tuple[list[dict], list[str], str]:
    """Turn the agent's reply into concrete file changes (not yet written)."""
    pending: dict[str, dict] = {}
    pd = plan_dir() + "/"

    def current(rel: str) -> str:
        if rel in pending:
            return pending[rel]["new"]
        try:
            p = note_target(rel)
            return p.read_text() if p.exists() else ""
        except ValueError:
            return ""

    for src, dst in RENAME_RE.findall(out):
        a, b = _rel(src), _rel(dst)
        a, b = (a if a.endswith(".md") else a + ".md"), (b if b.endswith(".md") else b + ".md")
        if a.startswith(pd) or b.startswith(pd) or a == b:
            continue
        pa = note_target(a)
        note_target(b)  # raises on paths outside the notes folder
        text = current(a)
        if not pa.exists() and a not in pending:
            continue
        old_b = current(b)
        # if a copy was already made under the new name, keep the newer content there
        pending[b] = {"path": b, "old": old_b, "new": old_b or text, "action": "renamed", "sections": [], "renamed_from": a}
        pending.pop(a, None)
        pending.setdefault("__deletes__", {"deletes": []})["deletes"].append(a)
    for path, content in FILE_RE.findall(out):
        rel = _rel(path)
        rel = rel if rel.endswith(".md") else rel + ".md"
        if rel.startswith(pd):
            continue
        note_target(rel)  # raises on paths outside the notes folder
        before = current(rel)
        pending[rel] = {"path": rel, "old": before, "new": normalize_math(content.rstrip("\n")) + "\n",
                        "action": "rewrote" if before else "created", "sections": []}
    for path, content in SECTION_RE.findall(out):
        rel = _rel(path)
        rel = rel if rel.endswith(".md") else rel + ".md"
        if rel.startswith(pd):
            continue
        note_target(rel)
        before = current(rel)
        new, old, action = apply_section(before, normalize_math(content))
        entry = pending.setdefault(rel, {"path": rel, "old": before, "new": before, "action": "updated", "sections": []})
        entry["new"] = new
        entry["sections"].append({"heading": content.strip().split("\n", 1)[0].lstrip("# ").strip(), "old": old,
                                  "action": action})
        if not before:
            entry["action"] = "created"
    rules = [r.strip() for r in RULE_RE.findall(out) if r.strip()]
    m = SUMMARY_RE.findall(out)
    summary = m[-1].strip() if m else ""
    deletes = pending.pop("__deletes__", {}).get("deletes", [])
    changes = list(pending.values())
    for d in deletes:
        changes.append({"path": d, "old": "", "new": None, "action": "removed (renamed)", "sections": []})
    return changes, rules, summary


def _save_rules(course: str, rules: list[str]):
    if not rules or course == GENERAL:
        return
    text = get_course_memory(course).rstrip() + "\n"
    head = "## Notes style for this course"
    if head not in text:
        text += f"\n{head}\n"
    lines = text.split("\n")
    i = lines.index(head) + 1
    while i < len(lines) and not lines[i].startswith("## "):
        i += 1
    while i > 0 and not lines[i - 1].strip() and lines[i - 1] is not lines[lines.index(head)]:
        i -= 1  # insert after the section's last item, not after its trailing blank line
    existing = text.lower()
    add = [f"- {r}" for r in rules if r.lower() not in existing]
    lines[i:i] = add
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"([^\n])\n(## )", r"\1\n\n\2", out)  # a blank line before every section heading
    out = re.sub(r"(## [^\n]+)\n\n(- )", r"\1\n\2", out)
    write_atomic(course_memory_path(course), out.strip() + "\n")


# ---------------- the cards under each answer ----------------

def _cards_path(cid: str) -> Path:
    return chat_dir(cid) / "notes_log.json"


def load_cards(cid: str) -> list[dict]:
    data = read_json(_cards_path(cid), [])
    return data if isinstance(data, list) else []


def _save_card(cid: str, card: dict):
    if not chat_dir(cid).exists():
        raise ChatGone()
    cards = [c for c in load_cards(cid) if c["id"] != card["id"]] + [card]
    write_atomic(_cards_path(cid), json.dumps(cards[-200:], indent=2))
    broadcast({"type": "notes_card", "chat": cid, "card": card})


# ---------------- one agent turn ----------------

async def _agent_turn(course: str, folder: str, message: str, images: list[str], files_for_context: list[str]) -> str:
    known = _folder_files(folder)
    ctx = [f"COURSE: {course}", f"COURSE NOTES FOLDER: notes/{folder}" if folder else "COURSE NOTES FOLDER: notes/ (no course)",
           "FILES IN THIS FOLDER:\n" + ("\n".join(f"- notes/{p}" for p in known[:200]) or "(none yet)")]
    budget = 36_000
    for rel in dict.fromkeys(files_for_context):
        try:
            p = note_target(rel)
        except ValueError:
            continue
        if not p.exists():
            continue
        body = p.read_text()
        if len(body) > MAX_FILE_CHARS:
            body = _outline_and_relevant(body, message)
        if budget - len(body) < 0:
            break
        budget -= len(body)
        ctx.append(f"CURRENT CONTENT of notes/{rel}:\n{body}")
    user = message + "\n\n" + "\n\n".join(ctx)
    system = render_prompt("notes_agent", course=None if course == GENERAL else course, course_name=course)
    convo = _history_for_model(course) + [{"role": "user", "content": user, "images": images}]
    out = ""
    for round_ in range(3):
        out = await llm.complete("notes", system, convo)
        calls = TOOL_RE.findall(out)
        if not calls or round_ == 2:
            break
        results = []
        for name, raw in calls[:4]:
            try:
                args = json.loads(raw) if raw else {}
                res = _read_note_tool(args) if name == "read_note" else "Unknown tool"
            except Exception as e:
                res = f"Tool error: {e}"
            results.append(f"### {name} {raw}\n{res}")
        convo = convo + [{"role": "assistant", "content": out}, {"role": "user", "content": "TOOL RESULTS:\n" + "\n\n".join(results)}]
    # remember the gist, not the full texts (they would be re-sent on every later turn)
    _, rules, summary = plan_changes(out, folder) if out else ([], [], "")
    edited = sorted({p for p, _ in SECTION_RE.findall(out)} | {p for p, _ in FILE_RE.findall(out)})
    gist = (f"SUMMARY: {summary or 'nothing to add'}" + (f"\nEdited: {', '.join(edited)}" if edited else "")
            + "".join(f"\nRULE: {r}" for r in rules))
    _append_history(course, {"role": "user", "content": _condense(message)}, {"role": "assistant", "content": gist})
    return out


async def _review(course: str, lesson: str, changes: list[dict]) -> dict:
    parts = []
    for c in changes:
        if c["new"] is None:
            parts.append(f"FILE notes/{c['path']} is removed because it was renamed (its content moved to the new name).")
            continue
        if c["sections"]:
            for s in c["sections"]:
                new_sec = c["new"]
                parts.append(f"FILE notes/{c['path']} · section “{s['heading']}” ({s['action']})\nOLD:\n{s['old'] or '(new section)'}\n"
                             f"NEW FILE CONTENT AROUND IT:\n{_around(new_sec, s['heading'])}")
        else:
            parts.append(f"FILE notes/{c['path']} ({c['action']})\nOLD:\n{c['old'][:20000] or '(new file)'}\nNEW:\n{c['new'][:20000]}")
    system = render_prompt("notes_reviewer", course=None if course == GENERAL else course)
    out = await llm.complete("reviewer", system, [{"role": "user", "content": f"LESSON:\n{lesson[:12000]}\n\nCHANGES:\n" + "\n\n".join(parts)}])
    return parse_json(out) or {"verdict": "approve", "issues": []}


def _shrunk(changes: list[dict]) -> list[dict]:
    return [c for c in changes if c["new"] is not None and c["action"] == "rewrote" and c["old"]
            and len(c["new"]) < 0.9 * len(c["old"])]


def _read_note_tool(args: dict) -> str:
    text = note_target(args["path"].removeprefix("notes/")).read_text()
    want = (args.get("heading") or "").strip().lstrip("#").strip().lower()
    if want:
        for h, sec in _sections(text):
            if h.lstrip("#").strip().lower() == want:
                return sec
        return f"No heading '{args.get('heading')}' in that note. Its outline:\n" + "\n".join(h for h, _ in _sections(text))
    if len(text) > 40_000:
        return (text[:40_000] + "\n\n(the note continues; ask for one section with {\"path\": ..., \"heading\": ...})")
    return text


def _sections(text: str) -> list[tuple[str, str]]:
    """(heading line, full section text) for every heading, outside code blocks."""
    lines = text.split("\n")
    heads, in_code = [], False
    for i, l in enumerate(lines):
        if l.strip().startswith("```"):
            in_code = not in_code
        if not in_code and _heading_level(l):
            heads.append(i)
    out = []
    for k, i in enumerate(heads):
        lvl = _heading_level(lines[i])
        end = next((j for j in heads[k + 1:] if _heading_level(lines[j]) <= lvl), len(lines))
        out.append((lines[i], "\n".join(lines[i:end])))
    return out


def _outline_and_relevant(body: str, message: str) -> str:
    """A long note as its outline plus the few sections that share the most words with this lesson.
    The agent can still read any section in full with read_note."""
    words = {w for w in re.findall(r"[a-zA-Z]{4,}", message.lower())}
    outline = "\n".join(h for h, _ in _sections(body))
    scored = []
    for h, sec in _sections(body):
        if _heading_level(h) <= 1 or len(sec) > SECTION_BUDGET:
            continue
        score = len(words & set(re.findall(r"[a-zA-Z]{4,}", sec.lower())))
        if score:
            scored.append((score, h, sec))
    picked, used = [], 0
    for score, h, sec in sorted(scored, key=lambda x: -x[0]):
        if used + len(sec) > SECTION_BUDGET or any(sec in p for p in picked):
            continue
        picked.append(sec)
        used += len(sec)
    return (f"(long note, {len(body)} characters: here is its outline and the sections most related to this lesson. "
            f"Use SECTION edits; read_note gives you the full text if you need it.)\nOUTLINE:\n{outline}\n\n"
            + "\n\n".join(picked))


def _around(text: str, heading: str) -> str:
    i = text.find(heading)
    if i < 0:
        return text[-6000:]
    return text[max(0, i - 200): i + 8000]


async def _process(cid: str, card: dict, course: str, folder: str, message: str, images: list[str],
                   context_files: list[str], lesson: str):
    settings = load_settings()
    out = await _agent_turn(course, folder, message, images, context_files)
    changes, rules, summary = plan_changes(out, folder)
    shrunk = _shrunk(changes)
    if shrunk:
        # a full rewrite that makes an existing note shorter probably dropped content: never save it as is
        card.update(status="fixing")
        _save_card(cid, card)
        out = await _agent_turn(course, folder, "NOT SAVED: your full rewrite would make these notes shorter, so content would be lost: "
                                + "; ".join(f"notes/{c['path']} ({len(c['old'])} → {len(c['new'])} characters)" for c in shrunk)
                                + ". Keep every existing line. Use SECTION edits for what changed, and output your edits again.",
                                [], [c["path"] for c in shrunk])
        changes, rules2, summary2 = plan_changes(out, folder)
        rules, summary = rules + rules2, summary2 or summary
        changes = [c for c in changes if c not in _shrunk(changes)]  # still shrinking: drop it rather than lose text
    if changes and settings.get("review_notes", True):
        card.update(status="reviewing")
        _save_card(cid, card)
        verdict = await _review(course, lesson, changes)
        issues = [i for i in verdict.get("issues") or [] if isinstance(i, dict)]
        card["review"] = {"verdict": verdict.get("verdict"), "issues": issues}
        if verdict.get("verdict") == "revise" and issues:
            card.update(status="fixing")
            _save_card(cid, card)
            fb = "\n".join(f"- notes/{i.get('file', '')}: [{i.get('type')}] {i.get('fix', '')}" for i in issues)
            out = await _agent_turn(course, folder, "NOTES REVIEWER: your last edit was NOT saved yet. Redo it with these fixes "
                                    "(output the full corrected edits again):\n" + fb, [], [c["path"] for c in changes])
            changes2, rules2, summary2 = plan_changes(out, folder)
            if changes2:
                changes, summary = changes2, summary2 or summary
            rules += rules2
    written = []
    for c in sorted(changes, key=lambda c: c["new"] is None):  # write the new name before removing the old one
        if c["new"] is None:
            try:
                p = note_target(c["path"])
                if p.exists() and any(w["path"] != c["path"] for w in written):
                    p.unlink()
            except (ValueError, OSError):
                pass
            continue
        write_note(c["path"], c["new"])
        written.append({"path": c["path"], "action": c["action"], **({"from": c["renamed_from"]} if c.get("renamed_from") else {}),
                        "sections": [{"heading": s["heading"], "action": s["action"]} for s in c["sections"]]})
    _save_rules(course, rules)
    card.update(status="done" if written else "nothing", files=written, summary=summary or ("Updated notes" if written else "Nothing new to add"),
                rules=card.get("rules", []) + rules, finished=time.time())
    _save_card(cid, card)
    if written:
        meta = load_meta(cid)
        meta["notes_touched"] = list(dict.fromkeys((meta.get("notes_touched") or []) + [w["path"] for w in written]))
        save_meta(meta)
        broadcast({"type": "notes", "paths": [w["path"] for w in written], "chat": cid})
    if rules:
        broadcast({"type": "memory", "summary": f"{course}: notes rule saved", "chat": cid})
    asyncio.create_task(_refresh_summary(course))


async def after_answer(cid: str, user_msg: dict, asst: dict):
    """Called after every reviewed tutor answer (when auto-notes is on)."""
    meta = load_meta(cid)
    course = course_of(meta)
    folder = course_folder(course)
    card = {"id": uuid.uuid4().hex[:10], "msg_ts": asst.get("ts"), "status": "working", "course": course,
            "folder": folder, "files": [], "summary": "", "corrections": [], "started": time.time()}
    lock = _locks.setdefault(course, asyncio.Lock())
    try:
        _save_card(cid, card)
        async with lock:
            touched = [p for p in (meta.get("notes_touched") or []) if not folder or p.startswith(folder + "/")][-3:]
            summary = read_summary(cid)
            message = (f"NEW LESSON from the chat “{meta.get('title') or 'untitled'}”"
                       + (f" (started from the plan task: {meta['task']})" if meta.get("task") else "")
                       + f"\n\nSTUDENT: {(user_msg.get('model_content') or user_msg.get('content') or '')[:8000]}"
                       + f"\n\nTUTOR (reviewed answer the student saw): {asst['content']}"
                       + (f"\n\nWHAT THIS CHAT COVERED BEFORE (summary): {summary[:4000]}" if summary else ""))
            lesson = f"STUDENT: {user_msg.get('content', '')[:6000]}\n\nTUTOR: {asst['content']}"
            await _process(cid, card, course, folder, message, user_msg.get("image_paths") or [], touched, lesson)
    except ChatGone:
        pass
    except Exception as e:
        card.update(status="error", summary=str(e)[:300])
        try:
            _save_card(cid, card)
        except Exception:
            pass


@router.post("/api/chats/{cid}/notes/{card_id}/feedback")
async def notes_feedback(cid: str, card_id: str, body: dict = Body(...)):
    """The student corrects a notes update: the agent fixes the note and may save a lasting rule."""
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "Write what should change.")
    card = next((c for c in load_cards(cid) if c["id"] == card_id), None)
    if not card:
        raise HTTPException(404, "That notes update was not found.")
    if card["status"] in ("working", "reviewing", "fixing"):
        raise HTTPException(409, "The Notes agent is still working on this. One moment.")
    card["corrections"] = card.get("corrections", []) + [{"text": text, "ts": time.time()}]
    card.update(status="working")
    _save_card(cid, card)

    async def run():
        course, folder = card["course"], card["folder"]
        lock = _locks.setdefault(course, asyncio.Lock())
        try:
            async with lock:
                files = [f["path"] for f in card.get("files") or []]
                message = (f"STUDENT FEEDBACK on your notes update ({', '.join(files) or 'nothing was saved'}): {text}\n"
                           "Apply it to the notes now. If it is a lasting preference for this course's notes, also save it as a RULE.")
                await _process(cid, card, course, folder, message, [], files, f"STUDENT FEEDBACK ON THE NOTES: {text}")
        except Exception as e:
            card.update(status="error", summary=str(e)[:300])
            _save_card(cid, card)
    asyncio.create_task(run())
    return card


async def direct_request(cid: str, text: str) -> dict:
    """/notes <request>: ask the course's Notes agent for something specific, right now."""
    from .chat import load_messages
    meta = load_meta(cid)
    course = course_of(meta)
    folder = course_folder(course)
    msgs = [m for m in load_messages(cid) if m.get("role") == "assistant"]
    card = {"id": uuid.uuid4().hex[:10], "msg_ts": msgs[-1]["ts"] if msgs else None, "status": "working", "course": course,
            "folder": folder, "files": [], "summary": "", "corrections": [{"text": text, "ts": time.time()}],
            "started": time.time()}
    _save_card(cid, card)

    async def run():
        lock = _locks.setdefault(course, asyncio.Lock())
        try:
            async with lock:
                touched = [p for p in (meta.get("notes_touched") or []) if not folder or p.startswith(folder + "/")][-3:]
                last = msgs[-1]["content"] if msgs else ""
                message = (f"STUDENT REQUEST from the chat “{meta.get('title') or 'untitled'}”: {text}\n\n"
                           + (f"LAST TUTOR ANSWER IN THAT CHAT: {last[:8000]}\n\n" if last else "")
                           + (f"CHAT SUMMARY: {read_summary(cid)[:4000]}" if read_summary(cid) else ""))
                await _process(cid, card, course, folder, message, [], touched, f"STUDENT REQUEST: {text}\n\nTUTOR: {last[:6000]}")
        except Exception as e:
            card.update(status="error", summary=str(e)[:300])
            _save_card(cid, card)
    asyncio.create_task(run())
    return card


__all__ = ["after_answer", "load_cards", "apply_section", "plan_changes"]
