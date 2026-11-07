"""Parsing <<<FILE blocks and writing notes safely."""
from __future__ import annotations

import re
from pathlib import Path

from .config import notes_dir

FILE_BLOCK = re.compile(r"<<<FILE\s+(.+?)\s*\n(.*?)\nFILE>>>", re.S)


def parse_file_blocks(text: str) -> list[tuple[str, str]]:
    out = []
    for m in FILE_BLOCK.finditer(text):
        path, content = m.group(1).strip().strip("`"), m.group(2)
        # Models sometimes wrap the whole content in a ```markdown fence
        stripped = content.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            stripped = re.sub(r"^```[a-zA-Z]*\n", "", stripped)[:-3]
            content = stripped
        out.append((path, content.rstrip() + "\n"))
    return out


def normalize_math(text: str) -> str:
    """Convert \\( \\) and \\[ \\] delimiters to $ / $$ (Obsidian + KaTeX syntax)."""
    text = re.sub(r"\\\[(.+?)\\\]", lambda m: "\n$$\n" + m.group(1).strip() + "\n$$\n", text, flags=re.S)
    text = re.sub(r"\\\((.+?)\\\)", lambda m: "$" + m.group(1).strip() + "$", text, flags=re.S)
    return text


def note_target(rel: str) -> Path:
    rel = rel.strip().lstrip("/")
    if rel.startswith("notes/"):
        rel = rel[len("notes/"):]
    if not rel.endswith(".md"):
        rel += ".md"
    root = notes_dir()
    p = (root / rel).resolve()
    if root not in p.parents:
        raise ValueError(f"Refusing to write outside the notes folder: {rel}")
    return p


def write_note(rel: str, content: str) -> Path:
    p = note_target(rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(normalize_math(content))
    return p


def notes_tree() -> list[dict]:
    root = notes_dir()
    out = []
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        out.append({"path": str(rel), "folder": str(rel.parent) if str(rel.parent) != "." else "",
                    "name": p.stem, "mtime": p.stat().st_mtime})
    return out
