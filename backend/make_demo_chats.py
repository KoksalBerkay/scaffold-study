"""Generate realistic demo chats through the real Tutor ⇄ Reviewer pipeline.

Output: demo-chats/ (committed). Machine-specific paths are replaced with placeholders so the
"Load demo" button can install them on any computer.

    cd backend && .venv/bin/python make_demo_chats.py
"""
import asyncio
import json
import shutil
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app import chat, materials  # noqa: E402
from app.config import load_settings, save_settings  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MAT = ROOT / "demo-materials"
OUT = ROOT / "demo-chats"

# Generate into demo-chats/ instead of the user's workspace
chat.CHATS = OUT / "chats"
chat.FOLDERS_FILE = chat.CHATS / "folders.json"
chat.UPLOADS = OUT / "uploads"

CHATS = [
    {
        "folder": "Linear Algebra", "title": "Parameter k in a linear system",
        "screenshot": ("Linear Algebra/Exams/LA_exam_2026-06-18.pdf", 2),
        "turns": [
            "Exercise 4 in this screenshot. I don't even know where to start with the k.",
            "Ok so I write the coefficient matrix and take its determinant? I got det = k³ − 3k + 2.",
            "Why does det = 0 mean the solution is not unique? We never really saw that in class.",
        ],
    },
    {
        "folder": "Linear Algebra", "title": "Gram-Schmidt on W",
        "pinned": "Linear Algebra/Exams/LA_exam_2026-06-18.pdf",
        "turns": [
            "Can you teach me Gram-Schmidt for Exercise 3? I only remember that it makes vectors orthogonal.",
            "First vector: u1 = (1,1,0)/√2. For the second one I just normalized (0,1,1) too, is that ok?",
        ],
    },
    {
        "folder": "Databases", "title": "Relational algebra: students in every course",
        "pinned": "Databases/Exams/DB_exam_2026-07-02.pdf",
        "task": "Databases · 2 July exam · Q3 · ~90 min: relational algebra and “every course”",
        "turns": [
            "I want to study this task from my plan: Databases · 2 July exam · Q3 · ~90 min: relational algebra and “every course”.\n\nTeach me from zero and guide me through it. Don't give me the answers.",
            "My idea: join Enrollment with Course on course id, select teacher = 'Rossi', then project the student name. Is that it?",
        ],
    },
    {
        "folder": "Databases", "title": "Trigger: max 3 active loans",
        "pinned": "Databases/Exams/DB_exam_2026-07-02.pdf",
        "turns": [
            "Q6, the trigger one. I've never written a trigger.",
            "CREATE TRIGGER max_loans AFTER INSERT ON Loan FOR EACH ROW BEGIN IF (SELECT COUNT(*) FROM Loan WHERE member_id = NEW.member_id) > 3 THEN SIGNAL SQLSTATE '45000'; END IF; END;",
        ],
    },
    {
        "folder": "Physics II", "title": "Moving loop and Lenz's law",
        "pinned": "Physics II/Exams/Physics2_exam_2026-06-25.pdf",
        "turns": [
            "Problem 2 with the loop leaving the magnetic field. I need help with the emf and the direction.",
            "You skipped why the flux changes at all if the field is uniform.",
            "So the flux is Φ = B·L·x where x is the part still inside, and dΦ/dt = −B·L·v?",
        ],
    },
]


async def make(spec: dict):
    meta = chat.create_chat({
        "title": spec["title"], "task": spec.get("task"),
        "folder": chat.ensure_folder(spec["folder"]),
        "pinned_files": [(MAT / spec["pinned"]).as_uri()] if spec.get("pinned") else [],
    })
    for i, text in enumerate(spec["turns"]):
        atts = []
        if i == 0 and spec.get("screenshot"):
            f, page = spec["screenshot"]
            img = materials.render_page(MAT / f, page)
            chat.UPLOADS.mkdir(parents=True, exist_ok=True)
            uid = uuid.uuid4().hex[:16]
            shutil.copy(img, chat.UPLOADS / f"{uid}.png")
            (chat.UPLOADS / f"{uid}.json").write_text(json.dumps({"name": "Screenshot.png", "file": f"{uid}.png"}))
            atts = [{"id": uid, "name": "Screenshot.png", "kind": "image", "url": f"/api/uploads/{uid}"}]
        async for ev in chat.tutor_turn(meta["id"], {"text": text, "attachments": atts}, review=True, background_jobs=False):
            if ev.get("type") == "review":
                print(f"  {spec['title'][:30]:30} turn {i + 1}: review round {ev['round']} → {ev['verdict']}", flush=True)
        # keep the chat title we chose
        m = chat.load_meta(meta["id"])
        m["title"] = spec["title"]
        chat.save_meta(m)
    print("done:", spec["title"], flush=True)


def scrub():
    """Replace machine-specific paths with placeholders."""
    mat_uri, mat_path, up = MAT.resolve().as_uri(), str(MAT.resolve()), str(chat.UPLOADS.resolve())
    for f in OUT.rglob("*"):
        if f.is_file() and f.suffix in (".json", ".jsonl", ".md"):
            t = f.read_text()
            t2 = t.replace(mat_uri, "file://{{DEMO_MATERIALS}}").replace(mat_path, "{{DEMO_MATERIALS_PATH}}").replace(up, "{{UPLOADS}}")
            if t2 != t:
                f.write_text(t2)


async def main():
    s = load_settings()
    s["materials_path"] = str(MAT)
    save_settings(s)
    if OUT.exists():
        shutil.rmtree(OUT)
    await asyncio.gather(*(make(c) for c in CHATS))
    scrub()
    print("demo chats in", OUT)

asyncio.run(main())
