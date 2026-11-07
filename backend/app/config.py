"""Workspace paths, settings and prompt loading."""
from __future__ import annotations

import copy
import json
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = Path(os.environ.get("SCAFFOLD_WORKSPACE", ROOT / "workspace")).resolve()
DEFAULT_PROMPTS = Path(__file__).parent / "prompts"

PROMPT_NAMES = [
    "planner", "plan_updater", "tutor", "reviewer", "notetaker",
    "memory_updater", "summary", "math",
]

ROLES = ["planner", "tutor", "reviewer", "background"]

DEFAULT_SETTINGS = {
    "materials_path": "",
    "notes_path": "",  # empty = workspace/notes
    "auto_notes": True,
    "review": True,
    "max_review_rounds": 2,
    "providers": {
        "openai": {"api_key": ""},
        "anthropic": {"api_key": ""},
    },
    "roles": {
        "planner": {"provider": "codex", "model": "gpt-6-luna", "effort": "high"},
        "tutor": {"provider": "codex", "model": "gpt-6-luna", "effort": "high"},
        "reviewer": {"provider": "codex", "model": "gpt-6-luna", "effort": "medium"},
        "background": {"provider": "codex", "model": "gpt-6-luna", "effort": "medium"},
    },
}

_lock = threading.Lock()


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
        settings_path().write_text(json.dumps(merged, indent=2))
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


def get_memory() -> str:
    p = memory_path()
    return p.read_text() if p.exists() else DEFAULT_MEMORY


def render_prompt(name: str, **values: str) -> str:
    text = get_prompt(name)
    values.setdefault("math_rules", get_prompt("math"))
    values.setdefault("memory", get_memory())
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    return text
