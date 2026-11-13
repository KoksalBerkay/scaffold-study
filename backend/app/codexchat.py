"""Scaffold chats linked to a real Codex thread: the student's message goes into that thread, the Reviewer
checks Codex's answer (sending feedback back into the same thread), and the background agents run as usual."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from pathlib import Path

from fastapi import Body, HTTPException

from . import chat, codexlink, llm
from .chat import (ChatGone, append_message, broadcast, chat_course, expand_attachments, load_messages, load_meta,
                   review_loop, router, save_meta)
from .config import get_memory, load_settings, write_atomic
from .files import normalize_math
from .planner import plan_dir

TUTOR_HEADER = (
    "[Scaffold] Sent from Scaffold, the student's study app. Before the student sees your reply, a separate "
    "Reviewer checks it (correct? any skipped step or untaught prerequisite? answer given away?) and may send it back "
    "to you. Teach step by step as usual. Do not create, edit or append to note files, and do not include notes in your "
    "reply: Scaffold's Notes agent writes the notes from your reviewed reply. This replaces any earlier instruction in this "
    "chat to take notes yourself. Other files you may edit when the student asks.")
PLANNER_HEADER = (
    "[Scaffold] Sent from Scaffold's study planner. Keep the plan files in \"{plan}\" up to date as you normally do; "
    "Scaffold's plan page shows them.")
STEER_HEADER = ("[Scaffold] The student stopped your previous answer to add the message below. Take it into account, "
                "and still answer what they asked before.")
REVIEW_HEADER = ("[Scaffold Reviewer] The student has not seen your last reply yet. Rewrite it and fix these points. "
                 "Reply with the complete corrected message for the student only, without mentioning this review. "
                 "Do not write or edit any note files (Scaffold's Notes agent does that):\n")
_background: set[asyncio.Task] = set()
FILES_CAP = 8000  # of the Reviewer's 14000-character material: what edited files contain now


def display_messages(cid: str, meta: dict) -> list[dict]:
    """Codex's own history (turns made outside Scaffold) merged with Scaffold's turns, oldest first."""
    tid = (meta.get("codex") or {}).get("thread")
    native = [m for m in load_messages(cid) if m.get("ts", 0) >= (meta["codex"].get("linked") or 0) - 1]
    outside: list[dict] = []
    skip_answer = False
    for m in codexlink.history(tid):
        if m["role"] == "user":
            skip_answer = m["content"].lstrip().startswith(codexlink.SCAFFOLD_MARK)
            if not skip_answer:
                outside.append({**m, "content": codexlink.clean_user_text(m["content"])})
        elif m["role"] == "assistant":
            if not skip_answer:
                outside.append(m)
        else:
            outside.append(m)
    return sorted(outside + native, key=lambda m: m.get("ts") or 0)


def context_of(meta: dict) -> dict | None:
    if meta.get("codex"):
        info = codexlink.thread_info(meta["codex"]["thread"])
        return codexlink.context_usage(info) if info else None
    return meta.get("context")


def _numbered(lines: list[str], idx) -> str:
    return "\n".join(f"{i + 1:>5}  {lines[i]}" for i in idx)


def _changed_lines(diffs: list[str]) -> list[int]:
    """Line numbers (in the new file) of the regions the diffs touched."""
    out = []
    for d in diffs:
        for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", d, re.M):
            start, n = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
            out += list(range(start, start + max(n, 1)))
    return out


def _current_file(path: str, diffs: list[str], cap: int) -> str:
    """What the file contains on disk now, with line numbers: all of it, or around the edits if it is long."""
    p = Path(path)
    if not p.exists():
        return "(This file does not exist now: it was deleted or moved.)"
    try:
        raw = p.read_bytes()
    except OSError as e:
        return f"(Scaffold could not read this file: {e.strerror or e})"
    if b"\0" in raw[:8192]:
        return "(Binary file: content not shown.)"
    lines = raw.decode(errors="replace").splitlines()
    full = _numbered(lines, range(len(lines)))
    if len(full) <= cap:
        return full or "(The file is empty.)"
    near = sorted({i for c in _changed_lines(diffs) for i in range(c - 9, c + 8) if 0 <= i < len(lines)})
    if not near:
        return full[:cap] + "\n… (long file: only the start is shown)"
    parts, run = [], [near[0]]
    for i in near[1:]:
        if i == run[-1] + 1:
            run.append(i)
        else:
            parts.append(run)
            run = [i]
    parts.append(run)
    text = "(Long file: showing the edited regions as they are now.)\n" + "\n   …\n".join(_numbered(lines, r) for r in parts)
    return text if len(text) <= cap else text[:cap] + "\n…"


def reviewer_material(steps: list[dict], info: dict | None = None, since: float = 0) -> str:
    """What the Reviewer is told about the Tutor's tool use, rebuilt before every review round: the current content
    of every file the Tutor edited (read from disk now), then each step newest first, saying which outputs predate
    an edit. Ordered so that what matters most survives the Reviewer's size limit."""
    if not steps:
        return "The Tutor answered without running any tools."
    edited: dict[str, list[int]] = {}  # path -> steps that edited it
    for st in steps:
        if st["kind"] == "edit" and st.get("applied"):
            for e in st["edits"]:
                edited.setdefault(e["path"], []).append(st["n"])
    out = ["The Tutor (Codex) used normal tools in the student's project. Steps are numbered in the order they "
           "happened (step 1 came first). The Tutor's file edits are real and already saved to disk."]
    if edited:
        diffs = {p: [e["diff"] for st in steps if st["kind"] == "edit" for e in st["edits"] if e["path"] == p and e["diff"]]
                 for p in edited}
        cap = max(1500, FILES_CAP // len(edited))
        if info and any(not diffs[p] for p in edited) and any(Path(p).exists() and Path(p).stat().st_size > cap for p in edited):
            for p, ds in codexlink.turn_diffs(info, since).items():
                if p in diffs and not diffs[p]:
                    diffs[p] = ds
        out.append("CURRENT CONTENT OF THE FILES THE TUTOR EDITED (read from disk by Scaffold just now, after all the "
                   "Tutor's steps: this is what the files contain now):")
        used = 0
        for p in sorted(edited, key=lambda p: -edited[p][-1]):  # most recently edited first
            head = f"### {p} (edited in step {', '.join(map(str, edited[p]))})"
            if used >= FILES_CAP:
                out.append(head + "\n(Not shown: size limit.)")
                continue
            block = f"{head}\n{_current_file(p, diffs[p], min(cap, FILES_CAP - used))}"
            used += len(block)
            out.append(block)
        out.append("STEPS, NEWEST FIRST:")
    for st in reversed(steps):
        head = f"Step {st['n']} ({st['round']})"
        if st["kind"] == "edit":
            names = ", ".join(e["path"] for e in st["edits"]) or "a file"
            if not st.get("applied"):
                out.append(f"{head}: the Tutor tried to edit {names}, but the edit failed and was not applied.")
                continue
            verb = "deleted" if all(e["kind"] == "delete" for e in st["edits"]) else "edited"
            body = (f"{head}: the Tutor {verb} {names}. The edit is saved"
                    + ("." if verb == "deleted" else "; the file's current content is shown above."))
            ds = "\n".join(e["diff"] for e in st["edits"] if e["diff"])
            if ds:
                body += "\nWhat this edit changed:\n" + (ds if len(ds) <= 1500 else ds[:1500] + "\n…")
            out.append(body)
        else:
            later = sorted({Path(p).name for p, ns in edited.items() if any(n > st["n"] for n in ns)
                            and Path(p).name in st["text"]})
            note = (f"\n(OLDER OUTPUT: {', '.join(later)} was edited after this command, so this shows the file as it was "
                    "BEFORE that edit, not its current content.)") if later else ""
            out.append(f"{head}: {st['text']}{note}\n{st.get('output') or '(no output)'}")
    return "\n\n".join(out)


def _memory_block(meta: dict, course: str | None) -> tuple[str, str]:
    mem = get_memory(course)
    h = hashlib.sha1(mem.encode()).hexdigest()[:12]
    if meta["codex"].get("memory_hash") == h:
        return "", h
    return f"\n\nThe student's saved preferences (follow them from now on):\n{mem.strip()}", h


async def codex_turn(cid: str, body: dict, retry: bool = False, **_):
    usage: list = []
    llm.usage_var.set(usage)
    meta = load_meta(cid)
    link = meta["codex"]
    info = codexlink.thread_info(link["thread"])
    if not info:
        raise llm.LLMError("This Codex chat no longer exists in Codex (it was deleted or archived).")
    if codexlink.busy(link["thread"]):
        raise llm.LLMError("This chat is busy in Codex right now. Wait until it finishes there, then try again.")
    planner = meta.get("kind") == "planner"
    settings = load_settings()
    course = chat_course(meta)
    activity: list[dict] = []
    t0 = time.time()

    def act(kind: str, text: str, **extra) -> dict:
        item = {"kind": kind, "text": text, "t": round(time.time() - t0, 1), **extra}
        activity.append(item)
        return {"type": "activity", **item}

    if retry:
        msgs = load_messages(cid)
        if not msgs or msgs[-1]["role"] != "user":
            raise ValueError("Nothing to retry.")
        user_msg = msgs[-1]
    else:
        text = (body.get("text") or "").strip()
        atts = body.get("attachments") or []
        extra_text, images = expand_attachments(atts)
        user_msg = {"role": "user", "content": text, "attachments": atts, "ts": time.time(), "image_paths": images,
                    "model_content": (text + ("\n\n" + extra_text if extra_text else "")) or "(see the attached images)"}
        if body.get("steer"):
            user_msg["steer"] = True
        append_message(cid, user_msg)
        broadcast({"type": "chats"})
    yield {"type": "user_saved"}
    if meta.get("last_error"):
        meta.pop("last_error", None)
        save_meta(meta)
    images = user_msg.get("image_paths") or []
    prior = [m for m in display_messages(cid, load_meta(cid)) if m is not user_msg and m.get("ts") != user_msg.get("ts")]
    # the Reviewer also sees screenshots sent in the last few messages (Codex itself remembers them)
    review_images = list(dict.fromkeys([p for m in prior[-6:] for p in (m.get("image_paths") or [])] + images))[-6:]

    header = PLANNER_HEADER.format(plan=plan_dir()) if planner else TUTOR_HEADER
    mem_block, mem_hash = ("", link.get("memory_hash")) if planner else _memory_block(meta, course)
    prompt = header + mem_block
    if user_msg.get("steer"):
        prompt += "\n\n" + STEER_HEADER
    prompt += "\n\n---\n\n" + user_msg["model_content"]

    model, effort = link.get("model") or info.get("model"), link.get("effort") or info.get("effort")
    label = " · ".join(x for x in (model, effort) if x)
    yield {"type": "status", "stage": "drafting", "detail": f"Codex is working in your chat ({label})"}
    yield act("draft", f"Sending to your Codex chat ({label})")

    steps: list[dict] = []  # commands and edits, in order, for the Reviewer
    round_label = ["first draft"]

    async def run(prompt_text: str, stage: str, imgs: list[str]):
        detail = "Codex is working"
        async for kind, val in codexlink.run_turn_any(info, prompt_text, imgs, model, effort):
            if kind == "tick":
                yield {"type": "status", "stage": stage, "detail": detail, "elapsed": val, "heartbeat": True}
            elif kind == "event":
                if val["kind"] == "thinking":
                    continue
                if val["kind"] == "output":
                    steps.append({"n": len(steps) + 1, "round": round_label[0], "kind": "command", "text": val["text"],
                                  "output": val.get("output")})
                    continue
                if val["kind"] == "edit":
                    steps.append({"n": len(steps) + 1, "round": round_label[0], "kind": "edit",
                                  "edits": val.get("edits") or [], "applied": val.get("applied", True)})
                detail = val["text"][:160]
                yield {"type": "status", "stage": stage, "detail": detail}
                yield act("compact" if val["kind"] == "compaction" else "tool", val["text"])
            elif kind == "final":
                yield ("result", val)

    draft = ""
    async for ev in run(prompt, "drafting", images):
        if isinstance(ev, tuple):
            draft = ev[1]
        else:
            yield ev
    meta = load_meta(cid)
    if meta.get("codex"):  # the chat may have been unlinked while Codex was answering: keep the answer anyway
        meta["codex"]["memory_hash"] = mem_hash
        save_meta(meta)
    yield act("draft", f"Codex answered ({len(draft.split())} words)")

    review = {"enabled": bool(settings.get("review")) and not planner, "rounds": [], "student_note": ""}
    if not planner:
        revisions = [0]

        async def revise(fb: str, n: int):
            revisions[0] += 1
            round_label[0] = f"revision {revisions[0]}"
            async for ev in run(REVIEW_HEADER + fb, "revising", []):
                yield ev

        # rebuilt before every review round: it includes the revisions' steps and reads edited files as they are now
        def material() -> str:
            return reviewer_material(steps, info, t0)
        async for ev in review_loop(draft, user_msg, prior, material, review_images, course, settings, act, revise, review):
            if isinstance(ev, tuple):
                draft = ev[1]
            else:
                yield ev

    final = normalize_math(draft)
    asst = {"role": "assistant", "content": final, "ts": time.time(), "review": review if not planner else None,
            "activity": activity, "seconds": round(time.time() - t0), "via": "codex",
            "compacted": any(a["kind"] == "compact" for a in activity), "plan_link": planner or None,
            "usage": llm.usage_summary(usage)}
    append_message(cid, asst)
    yield {"type": "message", "message": asst}
    broadcast({"type": "chats"})
    if planner:
        broadcast({"type": "plan"})
    else:
        task = asyncio.create_task(chat.background(cid, user_msg, asst))
        _background.add(task)  # the event loop keeps only a weak reference to a task
        task.add_done_callback(_background.discard)


# ---------------- linking ----------------

@router.get("/api/codex/threads")
def codex_threads():
    if not codexlink.available():
        return {"available": False, "projects": []}
    linked = {}
    for d in chat.CHATS.iterdir() if chat.CHATS.exists() else []:
        m = d / "meta.json"
        if m.exists():
            meta = chat.read_json(m) or {}
            if isinstance(meta, dict) and meta.get("codex"):
                linked[meta["codex"]["thread"]] = {"chat": meta["id"], "kind": meta.get("kind")}
    projects: dict[str, list] = {}
    for t in codexlink.list_threads():
        t["linked"] = linked.get(t["id"])
        projects.setdefault(t["project"], []).append(t)
    return {"available": True, "projects": [{"name": k, "threads": v} for k, v in projects.items()]}


@router.post("/api/codex/link")
def codex_link(body: dict = Body(...)):
    tid = body.get("thread") or ""
    info = codexlink.thread_info(tid)
    if not info:
        raise HTTPException(404, "That Codex chat was not found.")
    link = {"thread": tid, "cwd": info["cwd"], "model": info.get("model"), "effort": info.get("effort"),
            "linked": time.time()}
    if body.get("as_planner"):
        from .planchat import PLAN_CHAT_ID, ensure_plan_chat
        meta = ensure_plan_chat()
        d = chat.chat_dir(PLAN_CHAT_ID)
        tr = d / "transcript.jsonl"
        if tr.exists():  # keep Scaffold's own planner conversation, but out of the way
            tr.rename(d / f"transcript.before-codex-{int(time.time())}.jsonl")
        meta["codex"] = link
        meta["title"] = info["title"] or meta.get("title")
        save_meta(meta)
        broadcast({"type": "plan"})
        return meta
    for d in chat.CHATS.iterdir() if chat.CHATS.exists() else []:
        m = chat.read_json(d / "meta.json") if (d / "meta.json").exists() else None
        if isinstance(m, dict) and (m.get("codex") or {}).get("thread") == tid:
            raise HTTPException(409, "This Codex chat is already linked.")
    meta = chat.create_chat({"title": info["title"], "folder": body.get("folder")})
    meta["codex"] = link
    save_meta(meta)
    broadcast({"type": "chats"})
    return meta


@router.post("/api/chats/{cid}/codex")
def codex_settings(cid: str, body: dict = Body(...)):
    """Change the model or reasoning used for this linked Codex chat, or unlink it."""
    meta = load_meta(cid)
    if not meta.get("codex"):
        raise HTTPException(400, "This chat is not linked to Codex.")
    if body.get("unlink"):
        meta.pop("codex")
    else:
        for k in ("model", "effort"):
            if body.get(k):
                meta["codex"][k] = body[k]
    p = chat.chat_dir(cid) / "meta.json"
    write_atomic(p, json.dumps(meta, indent=2))
    return meta


__all__ = ["codex_turn", "display_messages", "context_of", "ChatGone"]
