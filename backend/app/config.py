"""Workspace paths, settings and prompt loading."""
from __future__ import annotations

import copy
import json
import os
import re
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = Path(os.environ.get("SCAFFOLD_WORKSPACE", ROOT / "workspace")).resolve()
DEFAULT_PROMPTS = Path(__file__).parent / "prompts"

PROMPT_NAMES = [
    "planner_chat", "planner", "plan_updater", "tutor", "reviewer", "notes_agent", "notes_reviewer",
    "memory_updater", "summary", "math",
]

ROLES = ["planner", "tutor", "reviewer", "notes", "background"]

DEFAULT_SETTINGS = {
    "materials_path": "",
    "notes_path": "",  # empty = workspace/notes
    "plan_folder": "",  # inside the notes folder; empty = "Study Plan"
    "auto_notes": True,
    "review_notes": True,  # the Notes reviewer checks every notes change before it is saved
    "review": True,
    "max_review_rounds": 2,
    "providers": {
        "openai": {"api_key": ""},
        "anthropic": {"api_key": ""},
    },
    "roles": {
        "planner": {"provider": "codex", "model": "gpt-6-luna", "effort": "high"},
        "tutor": {"provider": "codex", "model": "gpt-6-luna", "effort": "high"},
        "reviewer": {"provider": "codex", "model": "gpt-6-luna", "effort": "high"},
        "notes": {"provider": "codex", "model": "gpt-6-luna", "effort": "high"},
        "background": {"provider": "codex", "model": "gpt-6-luna", "effort": "medium"},
    },
}

_lock = threading.Lock()


def write_atomic(path: Path, text: str):
    """Write a file so readers never see it half-written (temp file + rename)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def read_json(path: Path, default=None):
    """Read JSON, returning `default` if the file is missing or unreadable."""
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


def _deep_merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def settings_path() -> Path:
    return WORKSPACE / "settings.json"


def load_settings() -> dict:
    p = settings_path()
    data = {}
    if p.exists():
        try:
            data = json.loads(p.read_text())
        except Exception:
            data = {}
    return _deep_merge(DEFAULT_SETTINGS, data)


def save_settings(s: dict) -> dict:
    with _lock:
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        merged = _deep_merge(DEFAULT_SETTINGS, s)
        write_atomic(settings_path(), json.dumps(merged, indent=2))
        return merged


def notes_dir() -> Path:
    s = load_settings()
    p = Path(s["notes_path"]).expanduser() if s.get("notes_path") else WORKSPACE / "notes"
    p.mkdir(parents=True, exist_ok=True)
    return p.resolve()


def materials_dir() -> Path | None:
    s = load_settings()
    if not s.get("materials_path"):
        return None
    p = Path(s["materials_path"]).expanduser()
    return p.resolve() if p.exists() else None


def prompt_path(name: str) -> Path:
    return WORKSPACE / "prompts" / f"{name}.md"


def get_prompt(name: str) -> str:
    p = prompt_path(name)
    if p.exists():
        return p.read_text()
    return (DEFAULT_PROMPTS / f"{name}.md").read_text()


def default_prompt(name: str) -> str:
    return (DEFAULT_PROMPTS / f"{name}.md").read_text()


def memory_path() -> Path:
    return WORKSPACE / "memory.md"


DEFAULT_MEMORY = """## Teaching preferences

## Things to never skip

## Known mistakes to watch for
"""

DEFAULT_COURSE_MEMORY = """## Teaching preferences for this course

## Notes style for this course

## Known mistakes to watch for
"""


def course_slug(course: str) -> str:
    slug = re.sub(r"[^\w\- ]+", "", course or "").strip()
    return slug[:80] or "course"


def course_memory_path(course: str) -> Path:
    return WORKSPACE / "memory" / f"{course_slug(course)}.md"


def get_course_memory(course: str) -> str:
    p = course_memory_path(course)
    return p.read_text() if p.exists() else DEFAULT_COURSE_MEMORY


def list_course_memories() -> list[str]:
    d = WORKSPACE / "memory"
    return sorted(p.stem for p in d.glob("*.md")) if d.exists() else []


def get_memory(course: str | None = None) -> str:
    """The general memory, plus the course's own memory when the chat belongs to a course."""
    p = memory_path()
    text = p.read_text() if p.exists() else DEFAULT_MEMORY
    if course:
        text = (f"# General (all courses)\n{text.strip()}\n\n"
                f"# Only for {course}\n{get_course_memory(course).strip()}\n")
    return text


def render_prompt(name: str, course: str | None = None, **values: str) -> str:
    text = get_prompt(name)
    values.setdefault("math_rules", get_prompt("math"))
    values.setdefault("memory", get_memory(course))
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    return text
