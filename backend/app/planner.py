"""Study planner: setup wizard → Context / Time Estimates / Study Plan / Quick Plan."""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import re
from pathlib import Path

from . import llm, materials
from .config import WORKSPACE, notes_dir, render_prompt
from .files import parse_file_blocks, write_note

PLAN_DIR = "Study Plan"
PLAN_FILES = ["Quick Plan", "Study Plan", "Time Estimates", "Context"]


def setup_path() -> Path:
    return WORKSPACE / "planner_setup.json"


def load_setup() -> dict | None:
    p = setup_path()
    return json.loads(p.read_text()) if p.exists() else None


def plan_file(name: str) -> Path:
    return notes_dir() / PLAN_DIR / f"{name}.md"


def read_plan() -> dict[str, str]:
    return {n: plan_file(n).read_text() for n in PLAN_FILES if plan_file(n).exists()}


def today_str() -> str:
    d = dt.date.today()
    return f"{d.isoformat()} ({d.strftime('%A')})"


async def with_heartbeat(coro, stage: str, detail: str = ""):
    """Run a coroutine, yielding progress events every second; the last item is ('result', value)."""
    task = asyncio.create_task(coro)
    start = asyncio.get_event_loop().time()
    try:
        while not task.done():
            yield {"type": "status", "stage": stage, "detail": detail, "heartbeat": True,
                   "elapsed": round(asyncio.get_event_loop().time() - start)}
            await asyncio.wait({task}, timeout=1.0)
        yield ("result", task.result())
    finally:
        if not task.done():
            task.cancel()


def _format_setup(setup: dict) -> str:
    lines = []
    lines.append(f"Plan period: {setup.get('start')} to {setup.get('end')}")
    lines.append(f"Hours per study day: {setup.get('hours_per_day')}")
    lines.append(f"Study days: {', '.join(setup.get('days') or []) or 'every day'}")
    lines.append(f"Typical session length: {setup.get('session_minutes')} min")
    lines.append("Courses:")
    for c in setup.get("courses", []):
        if not c.get("included", True):
            continue
        lines.append(
            f"- {c['name']}: exam date {c.get('exam_date') or 'unknown'}; credits {c.get('credits') or 'unknown'}; "
            f"confidence: {c.get('confidence') or 'unknown'}"
            + (f"; note: {c['note']}" if c.get("note") else ""))
    if setup.get("preferences"):
        lines.append(f"Student preferences, in their words: {setup['preferences']}")
    return "\n".join(lines)


async def _write_blocks(text: str) -> list[str]:
    written = []
    for path, content in parse_file_blocks(text):
        name = Path(path).stem
        if name not in PLAN_FILES:
            continue
        write_note(f"{PLAN_DIR}/{name}.md", content)
        written.append(name)
    return written


async def generate(setup: dict):
    root = Path(setup["materials_path"]).expanduser()
    setup_path().parent.mkdir(parents=True, exist_ok=True)
    setup_path().write_text(json.dumps(setup, indent=2))

    yield {"type": "status", "stage": "scan", "detail": "Reading every file in your materials folder"}
    courses = await asyncio.to_thread(materials.scan, root)
    include = {c["name"] for c in setup.get("courses", []) if c.get("included", True)}
    inventory = await asyncio.to_thread(materials.inventory_text, root, courses, include)
    n_files = sum(len(c["files"]) for c in courses if c["name"] in include)
    yield {"type": "status", "stage": "scan", "detail": f"Inventory ready: {n_files} files in {len(include)} courses"}

    system = render_prompt("planner", today=today_str())
    existing = read_plan()
    user = "SETUP:\n" + _format_setup(setup) + "\n\nINVENTORY:\n" + inventory
    if existing:
        user += "\n\nEXISTING FILES:\n" + "\n\n".join(f"### {k}.md\n{v}" for k, v in existing.items())
    else:
        user += "\n\nEXISTING FILES: none (first plan)."

    text = None
    async for ev in with_heartbeat(llm.complete("planner", system, [{"role": "user", "content": user}]),
                                   "thinking", "Estimating time per question and building your plan"):
        if isinstance(ev, tuple):
            text = ev[1]
        else:
            yield ev
    written = await _write_blocks(text)
    if "Quick Plan" not in written:
        raise llm.LLMError("The planner did not return a Quick Plan. Try again or switch the planner model.")
    yield {"type": "done", "written": written}


async def log_progress(text: str):
    existing = read_plan()
    if not existing:
        raise llm.LLMError("No plan yet. Create one first.")
    ticked = []
    qp = existing.get("Quick Plan", "")
    for line in qp.splitlines():
        if re.match(r"\s*- \[[xX]\]", line):
            ticked.append(line.strip())
    system = render_prompt("plan_updater", today=today_str())
    user = ("PLAN FILES:\n" + "\n\n".join(f"<<<FILE notes/{PLAN_DIR}/{k}.md\n{v}\nFILE>>>" for k, v in existing.items())
            + "\n\nTICKED TASKS IN THE APP:\n" + ("\n".join(ticked) or "(none)")
            + "\n\nSTUDENT'S PROGRESS LOG:\n" + text)
    out = None
    async for ev in with_heartbeat(llm.complete("planner", system, [{"role": "user", "content": user}]),
                                   "thinking", "Recalibrating estimates and rescheduling"):
        if isinstance(ev, tuple):
            out = ev[1]
        else:
            yield ev
    written = await _write_blocks(out)
    yield {"type": "done", "written": written}


def toggle(line: int, checked: bool, name: str = "Quick Plan", text: str | None = None) -> str:
    """Tick a checklist line. `text` (the task as the UI saw it) guards against stale line numbers."""
    p = plan_file(name)
    lines = p.read_text().split("\n")
    i = line - 1
    norm = lambda t: re.sub(r"^\s*[-*] \[[ xX]\]\s*", "", t).strip()  # noqa: E731
    if text is not None and not (0 <= i < len(lines) and norm(lines[i]) == norm(text)):
        matches = [j for j, l in enumerate(lines) if re.match(r"\s*[-*] \[[ xX]\]", l) and norm(l) == norm(text)]
        if not matches:
            raise ValueError("This task changed since the page loaded. Reload the plan and try again.")
        i = matches[0]
    if not (0 <= i < len(lines)) or not re.match(r"\s*[-*] \[[ xX]\]", lines[i]):
        raise ValueError("That line is not a checklist item")
    lines[i] = re.sub(r"\[[ xX]\]", "[x]" if checked else "[ ]", lines[i], count=1)
    p.write_text("\n".join(lines))
    return p.read_text()
