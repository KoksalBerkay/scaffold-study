"""The study-plan conversation: the Planner talks with the student to build the plan, then keeps it updated.

It is a normal chat (fixed id) with kind "planner". Its turns can end with a machine-readable block:
  <<<SETUP {...}SETUP>>>  build or rebuild the plan with this setup
  <<<UPDATE ...UPDATE>>>  run the plan updater with this progress report
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from . import chat, llm, materials, planner
from .config import load_settings, materials_dir, render_prompt

PLAN_CHAT_ID = "studyplanner"
GREETING = (
    "Hi! I'm your **study planner**. I'll build a plan you can actually follow, from your real past exams.\n\n"
    "First, show me your materials: choose the folder that has **one subfolder per course** "
    "(past exams, solutions, slides, exercise sheets). I'll read every file. Then we'll talk about your exams and your time."
)

SETUP_RE = re.compile(r"<<<SETUP\s*(\{.*?\})\s*(?:SETUP>>>|>>>|\Z)", re.S)
UPDATE_RE = re.compile(r"<<<UPDATE\s*(.*?)\s*(?:UPDATE>>>|>>>|\Z)", re.S)


def ensure_plan_chat() -> dict:
    d = chat.CHATS / PLAN_CHAT_ID
    if (d / "meta.json").exists():
        return chat.load_meta(PLAN_CHAT_ID)
    meta = {"id": PLAN_CHAT_ID, "title": "Study plan chat", "kind": "planner", "created": time.time(),
            "pinned_files": [], "notes_touched": [], "folder": None}
    chat.save_meta(meta, create=True)
    chat.append_message(PLAN_CHAT_ID, {"role": "assistant", "content": GREETING, "ts": time.time()})
    return meta


def materials_summary() -> str:
    root = materials_dir()
    if not root:
        return "No materials folder chosen yet. Ask the student to choose it with the button above the message box."
    courses = materials.scan(root)
    if not courses:
        return f"The folder {root} has no readable files (PDF, images, markdown, text)."
    out = [f"Materials folder: {root}"]
    for c in courses:
        counts = ", ".join(f"{n} {k}" for k, n in sorted(c["counts"].items()))
        out.append(f"- Course folder \"{c['name']}\": {len(c['files'])} files ({counts})")
        exams = sorted([f for f in c["files"] if f["kind"] == "exam"], key=lambda f: f["date"] or "", reverse=True)
        for f in exams[:12]:
            bits = [f["name"], f"{f['pages']} p."]
            if f["date"]:
                bits.append(f"dated {f['date']}")
            if f["questions"]:
                bits.append(f"~{f['questions']} numbered items")
            out.append("    past exam: " + ", ".join(bits))
        if len(exams) > 12:
            out.append(f"    … and {len(exams) - 12} more past exams")
    return "\n".join(out)


def _context() -> str:
    parts = ["## The student's materials", materials_summary()]
    setup = planner.load_setup()
    parts += ["## Current plan setup", json.dumps(setup, ensure_ascii=False) if setup else "No plan yet."]
    plan = planner.read_plan()
    if plan.get("Quick Plan"):
        parts += ["## Current Quick Plan (this week)", plan["Quick Plan"][:5000]]
    return "\n\n".join(parts)


def _clean_setup(raw: dict) -> dict:
    s = load_settings()
    setup = dict(raw)
    setup["materials_path"] = setup.get("materials_path") or s.get("materials_path") or ""
    days = [d[:3].title() for d in setup.get("days") or [] if isinstance(d, str)]
    setup["days"] = [d for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] if d in days] or ["Mon", "Tue", "Wed", "Thu", "Fri"]
    try:
        setup["hours_per_day"] = float(setup.get("hours_per_day") or 2)
    except Exception:
        setup["hours_per_day"] = 2.0
    setup["session_minutes"] = int(float(setup.get("session_minutes") or 90))
    setup["courses"] = [c for c in setup.get("courses") or [] if isinstance(c, dict) and c.get("name")]
    for c in setup["courses"]:
        c.setdefault("included", True)
    return setup


def _first_days(n: int = 2) -> str:
    qp = planner.read_plan().get("Quick Plan", "")
    days = re.split(r"\n(?=### )", qp)
    out = []
    for block in days[1:n + 1]:
        lines = block.strip().splitlines()
        out.append(f"**{lines[0].lstrip('# ').strip()}**")
        for l in lines[1:4]:
            if l.strip().startswith("- ["):
                item = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", l.strip())
                out.append(re.sub(r"^- \[[ xX]\]\s*", "- ", item))
    return "\n".join(out)


def _latest_update() -> str:
    ctx = planner.read_plan().get("Context", "")
    m = re.search(r"## Updates\s*\n(.*?)(?:\n## |\Z)", ctx, re.S)
    if not m:
        return ""
    entries = [e for e in re.split(r"\n(?=[-*] |### )", m.group(1).strip()) if e.strip()]
    return entries[0].strip() if entries else ""


async def planchat_turn(cid: str, body: dict, retry: bool = False, **_):
    meta = ensure_plan_chat()
    activity: list[dict] = []
    t0 = time.time()

    def act(kind, text, **extra):
        item = {"kind": kind, "text": text, "t": round(time.time() - t0, 1), **extra}
        activity.append(item)
        return {"type": "activity", **item}

    if retry:
        msgs = chat.load_messages(cid)
        if not msgs or msgs[-1]["role"] != "user":
            raise ValueError("Nothing to retry.")
        prior = msgs[:-1]
        user_msg = msgs[-1]
    else:
        text = (body.get("text") or "").strip()
        user_msg = {"role": "user", "content": text, "ts": time.time()}
        prior = chat.load_messages(cid)
        chat.append_message(cid, user_msg)
    yield {"type": "user_saved"}
    if meta.get("last_error"):
        meta.pop("last_error", None)
        chat.save_meta(meta)

    yield {"type": "status", "stage": "context", "detail": "Looking at your materials and your plan"}
    yield act("context", "Looking at your materials" + (" and your current plan" if planner.read_plan() else ""))
    system = render_prompt("planner_chat", today=planner.today_str()) + "\n\n# What you can see\n" + _context()
    history = [{"role": m["role"], "content": m["content"]} for m in (prior + [user_msg])[-30:]]
    out = None
    async for ev in planner.with_heartbeat(llm.complete("planner", system, history), "drafting", "The planner is thinking"):
        if isinstance(ev, tuple):
            out = ev[1]
        else:
            yield ev
    setup_m, update_m = SETUP_RE.search(out or ""), UPDATE_RE.search(out or "")
    visible = UPDATE_RE.sub("", SETUP_RE.sub("", out or "")).strip()
    if not visible:
        visible = ("Great, I'm building your plan now. It takes a few minutes: I read every exam question by question. "
                   "You can watch the progress below." if setup_m else
                   "Got it. I'm updating your plan now." if update_m else "Okay.")
    asst = {"role": "assistant", "content": visible, "ts": time.time(), "activity": list(activity)}
    chat.append_message(cid, asst)
    yield {"type": "message", "message": asst}

    if setup_m:
        try:
            setup = _clean_setup(json.loads(setup_m.group(1)))
        except Exception:
            note = {"role": "assistant", "content": "I couldn't read the plan settings I just made. Say **build it** and I'll try again.", "ts": time.time()}
            chat.append_message(cid, note)
            yield {"type": "message", "message": note}
            return
        if not setup["materials_path"] or not Path(setup["materials_path"]).expanduser().is_dir():
            note = {"role": "assistant", "content": "Choose your materials folder first (button above the message box), then say **build it**.", "ts": time.time()}
            chat.append_message(cid, note)
            yield {"type": "message", "message": note}
            return
        yield act("build", "Building your plan: reading every exam, estimating time per question, scheduling")
        async for ev in planner.generate(setup):
            if ev.get("type") == "status":
                ev = {**ev, "stage": "building"}
            if ev.get("type") != "done":
                yield ev
        yield act("done", "Wrote Quick Plan, Study Plan, Time Estimates and Context")
        msg = {"role": "assistant", "ts": time.time(), "activity": list(activity), "plan_link": True,
               "content": "✅ **Your plan is ready.** Here's how it starts:\n\n" + (_first_days() or "")
                          + "\n\nOpen **Study plan** to see the whole week. Each day, tick what you did or just tell me here how it went, and I'll adjust the plan."}
        chat.append_message(cid, msg)
        chat.broadcast({"type": "plan"})
        yield {"type": "message", "message": msg}
    elif update_m and update_m.group(1).strip():
        if not planner.read_plan():
            return
        yield act("update", "Updating your plan: recalibrating time estimates and rescheduling")
        async for ev in planner.log_progress(update_m.group(1).strip()):
            if ev.get("type") == "status":
                ev = {**ev, "stage": "building"}
            if ev.get("type") != "done":
                yield ev
        latest = _latest_update()
        msg = {"role": "assistant", "ts": time.time(), "activity": list(activity), "plan_link": True,
               "content": "✅ **Plan updated.**" + (f"\n\n{latest}" if latest else "") + "\n\nThe new schedule is in **Study plan**."}
        chat.append_message(cid, msg)
        chat.broadcast({"type": "plan"})
        yield {"type": "message", "message": msg}
