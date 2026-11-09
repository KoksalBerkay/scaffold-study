"""Load the demo semester into a workspace (command line only: `./run.sh --demo` does it for you).

    SCAFFOLD_WORKSPACE=../workspace-demo .venv/bin/python seed_demo.py

Safety rules:
- It only writes into the workspace's own notes folder. If Settings point the notes folder somewhere else
  (for example your Obsidian vault), it refuses.
- It never overwrites anything: existing notes, chats and settings are skipped.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from app import chat as chatmod
from app import planner
from app.config import ROOT, WORKSPACE, load_settings, notes_dir, save_settings

DEMO_NOTES = ROOT / "demo-notes"
DEMO_CHATS = ROOT / "demo-chats"
DEMO_MATERIALS = ROOT / "demo-materials"


def _fill(text: str, uploads: Path) -> str:
    return (text.replace("file://{{DEMO_MATERIALS}}", DEMO_MATERIALS.resolve().as_uri())
            .replace("{{DEMO_MATERIALS_PATH}}", str(DEMO_MATERIALS.resolve()))
            .replace("{{UPLOADS}}", str(uploads.resolve())))


def seed() -> dict:
    s = load_settings()
    if s.get("notes_path") and Path(s["notes_path"]).expanduser().resolve() != (WORKSPACE / "notes").resolve():
        raise SystemExit(f"Refusing: this workspace's notes folder is {s['notes_path']}. "
                         "Demo data only goes into a workspace's own notes folder. Use ./run.sh --demo.")
    root = notes_dir()
    written, skipped = [], []
    for f in sorted(DEMO_NOTES.rglob("*.md")) if DEMO_NOTES.is_dir() else []:
        rel = f.relative_to(DEMO_NOTES)
        dst = root / rel
        if dst.exists():
            skipped.append(str(rel))
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(_fill(f.read_text(), chatmod.UPLOADS))
        written.append(str(rel))

    chats = 0
    if (DEMO_CHATS / "chats").is_dir():
        chatmod.UPLOADS.mkdir(parents=True, exist_ok=True)
        for f in (DEMO_CHATS / "uploads").glob("*") if (DEMO_CHATS / "uploads").is_dir() else []:
            if not (chatmod.UPLOADS / f.name).exists():
                shutil.copy(f, chatmod.UPLOADS / f.name)
        folders_file = DEMO_CHATS / "chats" / "folders.json"
        demo_folders = json.loads(folders_file.read_text()) if folders_file.exists() else []
        remap = {f["id"]: chatmod.ensure_folder(f["name"]) for f in demo_folders}
        for d in sorted((DEMO_CHATS / "chats").iterdir()):
            if not d.is_dir() or (chatmod.CHATS / d.name).exists():
                continue
            dst = chatmod.CHATS / d.name
            dst.mkdir(parents=True)
            for f in d.iterdir():
                (dst / f.name).write_text(_fill(f.read_text(), chatmod.UPLOADS))
            meta = json.loads((dst / "meta.json").read_text())
            meta["folder"] = remap.get(meta.get("folder"))
            (dst / "meta.json").write_text(json.dumps(meta, indent=2))
            chats += 1

    if not s.get("materials_path"):
        s["materials_path"] = str(DEMO_MATERIALS)
        save_settings(s)
    setup_src = DEMO_NOTES / "planner_setup.json"
    if not planner.setup_path().exists() and setup_src.exists():
        setup = json.loads(setup_src.read_text())
        setup["materials_path"] = str(DEMO_MATERIALS)
        planner.setup_path().write_text(json.dumps(setup, indent=2))
    return {"workspace": str(WORKSPACE), "notes_written": len(written), "notes_skipped": len(skipped), "chats_added": chats}


if __name__ == "__main__":
    r = seed()
    print(f"Demo semester in {r['workspace']}: {r['notes_written']} notes added ({r['notes_skipped']} already there), "
          f"{r['chats_added']} chats added.", file=sys.stderr)
