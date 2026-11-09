"""Scaffold chats linked to a real Codex thread: the student's message goes into that thread, the Reviewer
checks Codex's answer (sending feedback back into the same thread), and the background agents run as usual."""
from __future__ import annotations

import asyncio
import hashlib
import json
import time

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
    "to you. Teach step by step as usual. Do not create or edit note files: Scaffold's Notes agent writes the notes "
    "from your reviewed reply. Other files you may edit when the student asks.")
PLANNER_HEADER = (
    "[Scaffold] Sent from Scaffold's study planner. Keep the plan files in \"{plan}\" up to date as you normally do; "
    "Scaffold's plan page shows them.")
STEER_HEADER = ("[Scaffold] The student stopped your previous answer to add the message below. Take it into account, "
                "and still answer what they asked before.")
REVIEW_HEADER = ("[Scaffold Reviewer] The student has not seen your last reply yet. Rewrite it and fix these points. "
                 "Reply with the complete corrected message for the student only, without mentioning this review:\n")


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


def _memory_block(meta: dict, course: str | None) -> tuple[str, str]:
    mem = get_memory(course)
    h = hashlib.sha1(mem.encode()).hexdigest()[:12]
    if meta["codex"].get("memory_hash") == h:
        return "", h
    return f"\n\nThe student's saved preferences (follow them from now on):\n{mem.strip()}", h


async def codex_turn(cid: str, body: dict, retry: bool = False, **_):
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

    header = PLANNER_HEADER.format(plan=plan_dir()) if planner else TUTOR_HEADER
    mem_block, mem_hash = ("", link.get("memory_hash")) if planner else _memory_block(meta, course)
    prompt = header + mem_block
    if user_msg.get("steer"):
        prompt += "\n\n" + STEER_HEADER
    prompt += "\n\n---\n\n" + user_msg["model_content"]

    model, effort = link.get("model") or info.get("model"), link.get("effort") or info.get("effort")
    label = " · ".join(x for x in (model, effort) if x)
    yield {"type": "status", "stage": "drafting", "detail": f"Codex is working in your chat ({label})"}
    yield act("draft", f"Sent to your Codex chat ({label})")

    async def run(prompt_text: str, stage: str, imgs: list[str]):
        detail = "Codex is working"
        async for kind, val in codexlink.run_turn(info, prompt_text, imgs, model, effort):
            if kind == "tick":
                yield {"type": "status", "stage": stage, "detail": detail, "elapsed": val, "heartbeat": True}
            elif kind == "event":
                if val["kind"] == "thinking":
                    continue
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
    meta["codex"]["memory_hash"] = mem_hash
    save_meta(meta)
    yield act("draft", f"Codex answered ({len(draft.split())} words)")

    review = {"enabled": bool(settings.get("review")) and not planner, "rounds": [], "student_note": ""}
    if not planner:
        async def revise(fb: str, n: int):
            async for ev in run(REVIEW_HEADER + fb, "revising", []):
                yield ev

        material = "Codex worked directly in the student's files. What it did:\n" + "\n".join(
            a["text"] for a in activity if a["kind"] in ("tool", "compact"))
        async for ev in review_loop(draft, user_msg, prior, material, images, course, settings, act, revise, review):
            if isinstance(ev, tuple):
                draft = ev[1]
            else:
                yield ev

    final = normalize_math(draft)
    asst = {"role": "assistant", "content": final, "ts": time.time(), "review": review if not planner else None,
            "activity": activity, "seconds": round(time.time() - t0), "via": "codex",
            "compacted": any(a["kind"] == "compact" for a in activity), "plan_link": planner or None}
    append_message(cid, asst)
    yield {"type": "message", "message": asst}
    broadcast({"type": "chats"})
    if planner:
        broadcast({"type": "plan"})
    else:
        asyncio.create_task(chat.background(cid, user_msg, asst))


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
