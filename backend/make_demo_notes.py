"""Generate pre-made demo notes (one Past Exams.md + one Foundations note per course) with the app's own
Note-taker prompt, using whichever model the 'background' role is set to. Output goes to demo-notes/."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app import llm, materials  # noqa: E402
from app.config import render_prompt  # noqa: E402
from app.files import parse_file_blocks, normalize_math  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MAT = ROOT / "demo-materials"
OUT = ROOT / "demo-notes"

ASK = """IMPORTANT: do not create or edit any files and do not use tools. Print every file in your reply as <<<FILE ... FILE>>> text blocks.

The student has worked through ALL the exercises of the past exams below with the tutor, reached every final answer, and wants complete notes.
Write the course's notes exactly as the Note-taker would after those sessions:
1. notes/{course}/Past Exams.md: every exercise of every paper (newest paper first), each with the original question word for word, a Solution that teaches from zero, and a Final Answer with a ^blockid. Fill Quick Links, Memorize and Solve again.
2. notes/{course}/{topic} - Foundations.md: one concept note for the course's central topic, linked from the exercises.
Use LaTeX for all math. Where the course has code (SQL, etc.), use fenced code blocks with the language. Use at least one table and one callout where they help.

PAST EXAMS AND MATERIAL (extracted text):
{material}
"""

TOPICS = {"Linear Algebra": "Eigenvalues and Diagonalization", "Databases": "SQL Grouping and Aggregation",
          "Physics II": "Gauss's Law"}


async def course(name: str):
    root = MAT / name
    material = "\n\n".join(f"### {p.relative_to(MAT)}\n" + materials.read_pages(p, None, 8000)
                           for p in sorted(root.rglob("*.pdf")))
    out = await llm.complete("background", render_prompt("notetaker"),
                             [{"role": "user", "content": ASK.format(course=name, topic=TOPICS[name], material=material)}])
    for path, content in parse_file_blocks(out):
        rel = path[len("notes/"):] if path.startswith("notes/") else path
        dst = OUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(normalize_math(content))
        print("wrote", dst.relative_to(ROOT))


async def main():
    names = sys.argv[1:] or list(TOPICS)
    await asyncio.gather(*(course(n) for n in names))

asyncio.run(main())
