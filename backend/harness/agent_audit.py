"""Agent audit: checks every agent against the mistakes students would hate, several times each.

    cd backend && .venv/bin/python -m harness.agent_audit            # all cases, 3 runs each
    .venv/bin/python -m harness.agent_audit --only reviewer --runs 5

It uses your current model settings but a throwaway workspace (your notes, chats and memory are never touched).
Each case has a hard check (code) and, where judgement is needed, a strict AI judge. A case passes only if
every run passes. Results go to test-runs/audit-<time>.json and a summary is printed.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REAL_WS = Path(os.environ.get("SCAFFOLD_WORKSPACE", ROOT / "workspace")).resolve()
TMP = Path(tempfile.mkdtemp(prefix="scaffold-audit-"))
_MODEL = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--model=")), "")
_REVIEWER = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--reviewer-model=")), "")
if (REAL_WS / "settings.json").exists():
    s = json.loads((REAL_WS / "settings.json").read_text())
    s.pop("notes_path", None)  # never write into the real notes folder
    s["materials_path"] = ""
    if _MODEL:  # e.g. --model=gpt-6-luna: every agent on that model (high reasoning, background medium)
        for role, cfg in s.get("roles", {}).items():
            s["roles"][role] = {"provider": "codex", "model": _MODEL, "effort": "medium" if role == "background" else "high"}
    if _REVIEWER:
        s.setdefault("roles", {})["reviewer"] = {"provider": "codex", "model": _REVIEWER, "effort": "high"}
    (TMP / "settings.json").write_text(json.dumps(s))
os.environ["SCAFFOLD_WORKSPACE"] = str(TMP)

from app import chat, llm, notesagent  # noqa: E402
from app.config import course_memory_path, memory_path, notes_dir, render_prompt, write_atomic  # noqa: E402,F401

COURSE = "Linear Algebra"


def _fixture_image() -> str:
    """A small screenshot of an exam schedule (generated, no real data)."""
    import pymupdf
    p = TMP / "exam-dates.png"
    if not p.exists():
        doc = pymupdf.open()
        page = doc.new_page(width=500, height=200)
        page.insert_text((20, 50), "Exam schedule (official)", fontsize=18)
        page.insert_text((20, 90), "Linear Algebra written exam: 26 January 2027, 9:00", fontsize=13)
        page.insert_text((20, 120), "Databases written exam: 3 February 2027, 14:00", fontsize=13)
        page.get_pixmap(dpi=110).save(str(p))
    return str(p)
SEM = asyncio.Semaphore(6)


# ---------------- helpers ----------------

async def judge(question: str, text: str) -> tuple[bool, str]:
    sys_ = ("You are a strict test judge. Answer only with JSON {\"pass\": true|false, \"why\": \"one sentence\"}. "
            "Judge exactly the question asked, nothing else.")
    out = await llm.complete("reviewer", sys_, [{"role": "user", "content": f"QUESTION: {question}\n\nTEXT TO JUDGE:\n{text}"}])
    d = chat.parse_json(out) or {}
    return bool(d.get("pass")), d.get("why", out[:200])


async def reviewer_verdict(student: str, draft: str, prior=None, rounds=None, memory: str = "", images=None, material: str = "") -> dict:
    rin = chat.review_input({"content": student}, prior or [], material, draft, rounds or [])
    out = await llm.complete("reviewer", render_prompt("reviewer", memory=memory or "## Teaching preferences\n"),
                             [{"role": "user", "content": rin, "images": images or []}])
    return chat.parse_json(out) or {"verdict": "unreadable", "issues": [], "raw": out[:500]}


def issues_text(v: dict) -> str:
    return "; ".join(f"[{i.get('type')}] {i.get('fix', '')}" for i in v.get("issues") or [])


# ---------------- reviewer cases ----------------

def R(name, student, draft, expect, prior=None, rounds=None, memory="", must_not=None, image=False, material=""):
    """expect: 'approve' or a set of acceptable issue types; must_not: words that must not appear in fixes."""
    async def run():
        v = await reviewer_verdict(student, draft, prior, rounds, memory, [_fixture_image()] if image else None, material)
        fixes = issues_text(v).lower()
        if v.get("verdict") == "unreadable":
            return False, "reviewer reply unreadable: " + v.get("raw", "")
        if must_not and any(w in fixes for w in must_not):
            return False, f"asked for something forbidden: {fixes[:300]}"
        if expect is None:  # only the must_not rule matters (e.g. never ask to shorten)
            return True, fixes[:300] or "approved"
        if expect == "approve":
            return v.get("verdict") != "revise", fixes[:300] or "approved"
        types = {i.get("type") for i in v.get("issues") or []}
        ok = v.get("verdict") == "revise" and bool(types & expect)
        return ok, f"verdict={v.get('verdict')} types={sorted(t for t in types if t)} {fixes[:200]}"
    return ("reviewer", name, run)


REVIEWER = [
    R("confirming the student's own correct result is fine",
      "I got lambda = 1 and lambda = 3 for [[2,1],[1,2]]. Is that right? Check it quickly with trace and determinant.",
      "Yes, $1$ and $3$ are correct. Their sum $1+3=4$ equals the trace $2+2=4$, and their product $1\\cdot3=3$ equals the determinant $2\\cdot2-1\\cdot1=3$. For a $2\\times2$ matrix, matching sum and product fixes both eigenvalues.\n\nNext: try $\\begin{pmatrix}4&1\\\\2&3\\end{pmatrix}$ the same way.",
      "approve"),
    R("a wrong number is caught",
      "I got lambda = 1 and lambda = 3 for [[2,1],[1,2]]. Is that right?",
      "Not quite. The determinant of $\\begin{pmatrix}2&1\\\\1&2\\end{pmatrix}$ is $2\\cdot2-1\\cdot1=4$, so the eigenvalues must multiply to $4$, and $1\\cdot3\\neq4$. Recompute $\\det(A-\\lambda I)$.",
      {"correctness", "feedback"}),
    R("giving the answer away is caught",
      "How do I find the eigenvalues of [[4,1],[2,3]]? I have no idea where to start.",
      "Form $A-\\lambda I=\\begin{pmatrix}4-\\lambda&1\\\\2&3-\\lambda\\end{pmatrix}$. Its determinant is $(4-\\lambda)(3-\\lambda)-2=\\lambda^2-7\\lambda+10=(\\lambda-5)(\\lambda-2)$, so the eigenvalues are $5$ and $2$.",
      {"gave_answer"}),
    R("a good first hint for a beginner is approved",
      "How do I find the eigenvalues of [[4,1],[2,3]]? I have no idea where to start.",
      "An **eigenvalue** of a square matrix $A$ is a number $\\lambda$ for which some nonzero vector $\\mathbf v$ satisfies $A\\mathbf v=\\lambda\\mathbf v$.\nRewrite it as $(A-\\lambda I)\\mathbf v=\\mathbf 0$, where $I$ is the identity matrix (ones on the diagonal, zeros elsewhere). A matrix is **invertible** when some matrix undoes it; then the only vector it sends to $\\mathbf 0$ is $\\mathbf 0$ itself. So a nonzero $\\mathbf v$ with $(A-\\lambda I)\\mathbf v=\\mathbf 0$ can exist only when $A-\\lambda I$ is not invertible, and for a square matrix that happens exactly when $\\det(A-\\lambda I)=0$. Solving that equation for $\\lambda$ gives the eigenvalues.\nFor a $2\\times2$ matrix, $\\det\\begin{pmatrix}a&b\\\\c&d\\end{pmatrix}=ad-bc$.\n\nYour first step: write $A-\\lambda I$ for your matrix by subtracting $\\lambda$ from each diagonal entry. What matrix do you get?",
      "approve"),
    R("a short answer the student asked to keep short is not padded",
      "Keep it short: what does the determinant of a 2x2 matrix tell me?",
      "For $\\begin{pmatrix}a&b\\\\c&d\\end{pmatrix}$ the determinant is $ad-bc$. Its absolute value is the factor by which the matrix scales areas, and its sign tells you whether the orientation flips. If it is $0$, the matrix squashes the plane onto a line or a point, so it has no inverse.\n\nNext: compute it for $\\begin{pmatrix}2&1\\\\1&3\\end{pmatrix}$.",
      "approve"),
    R("an earlier request for notes does not make the reviewer ask for notes",
      "Now explain what the trace of a 2x2 matrix is. Keep it short.",
      "The **trace** of a square matrix is the sum of its diagonal entries: for $\\begin{pmatrix}a&b\\\\c&d\\end{pmatrix}$ it is $a+d$. For a $2\\times2$ matrix it equals the sum of the two eigenvalues (the numbers $\\lambda$ for which some nonzero vector $\\mathbf v$ satisfies $A\\mathbf v=\\lambda\\mathbf v$), so it is a quick check on eigenvalues you computed.\n\nNext: what is the trace of $\\begin{pmatrix}2&1\\\\1&3\\end{pmatrix}$?",
      "approve",
      prior=[{"role": "user", "content": "Teach me step by step and after every answer append notes to notes.md."},
             {"role": "assistant", "content": "Okay, I will teach step by step."}],
      must_not=["notes.md", "append", "note "]),
    R("when memory allows it, giving the requested code is fine",
      "Just give me the code for the getter of my private double field `price`, I'm in a hurry.",
      "```java\npublic double getPrice() {\n    return price; // reads the private field\n}\n```\nIt returns the value stored in the `price` field, so callers can read it without changing it.",
      "approve",
      memory="## Teaching preferences\n- If I explicitly ask you to do it (\"just give me the code\"), do it.\n"),
    R("without that memory, a bare request for the answer is still refused",
      "Just tell me the eigenvalues of [[4,1],[2,3]], I don't want to do it.",
      "The eigenvalues are $\\lambda_1=5$ and $\\lambda_2=2$.",
      {"gave_answer"}),
    R("a fixed revision is approved, not argued again",
      "Actually keep it short: I got lambda = 1 and lambda = 3 for [[2,1],[1,2]]. Is that right? Check it with trace and determinant only.",
      "Yes, $1$ and $3$ are correct. Check: their sum $1+3=4$ equals the trace $2+2=4$, and their product $1\\cdot3=3$ equals the determinant $2\\cdot2-1\\cdot1=3$.\n\nNext: try $\\begin{pmatrix}4&1\\\\2&3\\end{pmatrix}$ the same way.",
      "approve",
      rounds=[{"verdict": "revise", "issues": [{"type": "feedback", "fix": "State clearly whether the student's values are correct before the check."}]}]),
    R("a question about a screenshot sent earlier is answered, not blocked",
      "And the Databases one?",
      "The Databases written exam is on **3 February 2027 at 14:00**, which is 33 days after 1 January 2027.",
      "approve", image=True,
      prior=[{"role": "user", "content": "What date is the Linear Algebra exam in this screenshot, and how many days after 1 January 2027 is it?"},
             {"role": "assistant", "content": "The Linear Algebra exam is on 26 January 2027, which is 25 days after 1 January 2027."}]),
    R("a logistics question is answered directly",
      "How long is it from my Linear Algebra exam on 26 January to my Databases exam on 3 February?",
      "There are **8 days** between 26 January and 3 February (5 days left in January, plus 3 in February).",
      "approve"),
    R("a long but correct explanation is never sent back to be shortened",
      "Can you explain what an eigenvector is? I have never seen it.",
      "An **eigenvector** of a square matrix $A$ is a nonzero vector $\\mathbf v$ that $A$ does not turn: $A$ only stretches, shrinks or flips it. In symbols, $A\\mathbf v=\\lambda\\mathbf v$ for some number $\\lambda$, called the **eigenvalue** that belongs to $\\mathbf v$.\n\n"
      "*Why this matters.* Most vectors change direction when you multiply them by a matrix. Eigenvectors are the special directions where the matrix acts like plain multiplication by a number, so along them the matrix is easy to understand.\n\n"
      "*Example.* For $A=\\begin{pmatrix}2&0\\\\0&3\\end{pmatrix}$ and $\\mathbf v=\\begin{pmatrix}1\\\\0\\end{pmatrix}$: $A\\mathbf v=\\begin{pmatrix}2\\\\0\\end{pmatrix}=2\\mathbf v$. So $\\mathbf v$ is an eigenvector with eigenvalue $2$. The vector $\\begin{pmatrix}1\\\\1\\end{pmatrix}$ is not one: $A$ sends it to $\\begin{pmatrix}2\\\\3\\end{pmatrix}$, which points in a different direction.\n\n"
      "*Why nonzero.* $A\\mathbf 0=\\lambda\\mathbf 0$ holds for every $\\lambda$, so allowing $\\mathbf 0$ would make every number an eigenvalue. That is why the definition excludes it.\n\n"
      "Next: check whether $\\begin{pmatrix}0\\\\1\\end{pmatrix}$ is an eigenvector of the same $A$, and if so, with which eigenvalue.",
      None, must_not=["shorter", "shorten", "trim", "concise", "remove", "cut ", "too long", "length"]),
    R("a tutor that read the student's files with the terminal is trusted",
      "I edited src/diet/Food.java: rawMaterials() now returns rawMaterialsByName.values(), and Java reports a type mismatch. Check my edit.",
      "Your edit returns a `Collection<RawMaterial>`, but `rawMaterials()` promises a `Collection<NutritionalElement>`. There are two separate problems. First, in your files `RawMaterial` does not implement `NutritionalElement` yet. Second, even after it does, Java will not treat a `Collection<RawMaterial>` as a `Collection<NutritionalElement>`: generic collections do not convert automatically, so we will fix the return line after the first step.\n\n**Next small step:** change `RawMaterial`'s declaration to `public class RawMaterial implements NutritionalElement {`. The interface then requires `public String getName()` (interface methods must be implemented as `public`); add it so it returns the `name` field.",
      "approve",
      material=("The Tutor (Codex) used normal tools in the student's project. These are the exact commands and what they returned: the Tutor saw all of this.\n\n"
                "$ cat src/diet/Food.java src/diet/RawMaterial.java src/diet/NutritionalElement.java\n"
                "package diet;\nimport java.util.*;\npublic class Food {\n    private Map<String, RawMaterial> rawMaterialsByName = new TreeMap<>();\n"
                "    public Collection<NutritionalElement> rawMaterials() {\n        return rawMaterialsByName.values();\n    }\n}\n"
                "package diet;\npublic class RawMaterial {\n    private String name;\n}\n"
                "package diet;\npublic interface NutritionalElement {\n    String getName();\n}"),
      must_not=["paste", "cannot see", "can't see", "cannot verify", "can't verify", "share the", "not shown"]),
    R("telling the exact code for one lab step is guidance, not answer-giving",
      "Okay, Java reports a type mismatch on rawMaterials(). What's the next step? (We're following the lab README.)",
      "The README says the returned raw materials are objects implementing `NutritionalElement`. An **interface** is a contract: a class that implements it promises to provide its methods, so its objects can be used wherever the interface type is expected.\n\n**Next step:** in `RawMaterial.java`, change the class declaration to `public class RawMaterial implements NutritionalElement {`. Java will then list the methods you must add; we'll do them one at a time. The collection mismatch is a separate fix after that.",
      "approve", must_not=["riddle", "hint instead", "do not give the exact", "don't give the exact"]),
    R("a subtle sign error is caught",
      "Can you check my determinant for [[3,-2],[4,1]]? I get 3*1 - (-2)*4 = 11.",
      "Almost: $\\det=3\\cdot1-(-2)\\cdot4=3-8=-5$. Watch the sign: subtracting a negative product.",
      {"correctness", "feedback"}),
    R("correct LaTeX-heavy teaching is not nitpicked for formatting",
      "Why is the projection of v onto a unit vector u equal to (v·u)u?",
      "The **projection** of $\\mathbf v$ onto $\\mathbf u$ is the point on the line through $\\mathbf u$ closest to $\\mathbf v$. Every point on that line is a scalar multiple $c\\,\\mathbf u$. The closest point is where the leftover $\\mathbf v-c\\mathbf u$ meets the line at a right angle: from any other point on the line, the leftover has an extra piece along the line, and by Pythagoras that makes it longer. Two vectors are perpendicular exactly when their dot product is $0$:\n$$\n(\\mathbf v-c\\mathbf u)\\cdot\\mathbf u=0\\;\\Longrightarrow\\;\\mathbf v\\cdot\\mathbf u-c\\,(\\mathbf u\\cdot\\mathbf u)=0.\n$$\nSince $\\mathbf u$ is a unit vector, $\\mathbf u\\cdot\\mathbf u=1$, so $c=\\mathbf v\\cdot\\mathbf u$ and the projection is $(\\mathbf v\\cdot\\mathbf u)\\mathbf u$.\n\nNext: compute it for $\\mathbf v=(1,0,1)$ and $\\mathbf u=\\tfrac{1}{\\sqrt2}(1,1,0)$.",
      "approve", must_not=["delimiter", "\\(", "format"]),
]


# ---------------- notes agent cases ----------------

EXISTING = """---
tags:
  - linear-algebra
---
# Eigenvalues - Foundations

## Characteristic polynomial from trace and determinant
For a $2\\times2$ matrix, $\\lambda^2-(\\operatorname{tr}A)\\lambda+\\det A=0$.
For $B=\\begin{pmatrix}3&-5\\\\2&1\\end{pmatrix}$: $\\operatorname{tr}B=4$, $\\det B=13$, so $\\lambda^2-4\\lambda+13=0$.

## Written by me
My own reminder: always check the trace first.
"""


def notes_setup():
    d = notes_dir() / COURSE
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    (d / "Eigenvalues - Foundations.md").write_text(EXISTING)
    hist = notesagent._hist_path(COURSE)
    if hist.exists():
        hist.unlink()
    return d


def N(name, message, check, files=("Linear Algebra/Eigenvalues - Foundations.md",)):
    async def run():
        notes_setup()
        out, _ = await notesagent._agent_turn(COURSE, COURSE, message, [], list(files))
        changes, rules, summary = notesagent.plan_changes(out, COURSE)
        return await check(changes, rules, summary, out)
    return ("notes", name, run)


async def keeps_everything(changes, rules, summary, out):
    for c in changes:
        if c["new"] is None:
            return False, f"deleted {c['path']}"
        if c["path"].endswith("Eigenvalues - Foundations.md"):
            for must in ("## Characteristic polynomial from trace and determinant", "\\lambda^2-4\\lambda+13", "My own reminder"):
                if must not in c["new"]:
                    return False, f"lost existing content: {must!r}"
    return True, summary or "kept everything"


async def lesson_recorded(changes, rules, summary, out):
    ok, why = await keeps_everything(changes, rules, summary, out)
    if not ok:
        return ok, why
    text = "\n".join(c["new"] or "" for c in changes)
    if "a+bi" not in text.replace(" ", "") and "a + bi" not in text and "a+b i" not in text:
        return False, "the lesson (a+bi form) was not recorded"
    return True, summary


async def nothing_written(changes, rules, summary, out):
    return (not changes), (summary or "nothing") if not changes else f"wrote {[c['path'] for c in changes]}"


async def no_unearned_answer(changes, rules, summary, out):
    text = "\n".join(c["new"] or "" for c in changes)
    if not text:
        return False, "nothing recorded at all"
    ok, why = await judge("Do these notes avoid stating the final eigenvalues of [[4,1],[2,3]] (which are 5 and 2) as a result? "
                          "Pass if the values 5 and 2 are NOT given as the eigenvalues of that matrix.", text)
    return ok, why


async def narrow_rule(changes, rules, summary, out):
    if any(c["new"] is None for c in changes) and not any(c.get("renamed_from") for c in changes):
        return False, "deleted a file"
    if not rules:
        return True, "no rule saved (fine: it was about one name)"
    ok, why = await judge("Is this saved rule narrow, i.e. only about spelling 'Gram-Schmidt' with a hyphen, and NOT a general "
                          "rule about hyphens in all file names? Rule: " + " | ".join(rules), " | ".join(rules))
    return ok, why


NOTES = [
    N("a new lesson is added without losing earlier content",
      "NEW LESSON from the chat “Complex eigenvalues”\n\nSTUDENT: How do I write complex eigenvalues in a + bi form?\n\n"
      "TUTOR (reviewed answer the student saw): Use $\\sqrt{-k}=i\\sqrt{k}$ for $k>0$, then divide both parts by the denominator. "
      "For example $\\frac{6\\pm\\sqrt{-16}}{2}=\\frac{6\\pm4i}{2}=3\\pm2i$, which means $3+2i$ and $3-2i$.",
      lesson_recorded),
    N("a lesson about a different matrix never deletes the old example",
      "NEW LESSON from the chat “Eigenvalues of A”\n\nSTUDENT: How do I find the eigenvalues of [[4,1],[2,3]]?\n\n"
      "TUTOR (reviewed answer the student saw): Form $A-\\lambda I$ and set $\\det(A-\\lambda I)=0$. For a $2\\times2$ matrix, "
      "$\\det\\begin{pmatrix}a&b\\\\c&d\\end{pmatrix}=ad-bc$. Your first step: write $A-\\lambda I$. What matrix do you get?",
      keeps_everything),
    N("small talk produces no notes",
      "NEW LESSON from the chat “Eigenvalues of A”\n\nSTUDENT: ok thanks, see you tomorrow\n\nTUTOR (reviewed answer the student saw): See you tomorrow! Next time we continue with diagonalization.",
      nothing_written),
    N("a result the student has not reached is not written as the answer",
      "NEW LESSON from the chat “Eigenvalues of A”\n\nSTUDENT: How do I find the eigenvalues of [[4,1],[2,3]]?\n\n"
      "TUTOR (reviewed answer the student saw): Form $A-\\lambda I=\\begin{pmatrix}4-\\lambda&1\\\\2&3-\\lambda\\end{pmatrix}$ and set its determinant to zero. "
      "Expand $(4-\\lambda)(3-\\lambda)-2$ and solve the quadratic yourself. What do you get?",
      no_unearned_answer),
    N("a correction about one name stays a narrow rule",
      "STUDENT FEEDBACK on your notes update (Linear Algebra/Gram Schmidt - Foundations.md): spell it Gram-Schmidt with the hyphen.\n"
      "Apply it to the notes now. If it is a lasting preference for this course's notes, also save it as a RULE.",
      narrow_rule, files=()),
]


# ---------------- memory updater cases ----------------

def M(name, prev, reply, expect_changed, expect_scope=None):
    async def run():
        write_atomic(memory_path(), "## Teaching preferences\n\n## Things to never skip\n\n## Known mistakes to watch for\n")
        cp = course_memory_path(COURSE)
        if cp.exists():
            cp.unlink()
        out = await llm.complete("background", render_prompt("memory_updater"),
                                 [{"role": "user", "content": chat.memory_input(COURSE, prev, reply)}])
        d = chat.parse_json(out) or {}
        changed = bool(d.get("changed"))
        if changed != expect_changed:
            return False, f"changed={changed} ({d.get('change_summary')})"
        scopes = sorted(chat.memory_updates(d, COURSE))  # new shape (general/course keys) or old (scope + memory)
        if expect_scope and scopes != [expect_scope]:
            return False, f"files={scopes} ({d.get('change_summary')})"
        return True, d.get("change_summary") or "no change"
    return ("memory", name, run)


PREV = "The determinant of a $2\\times2$ matrix is $ad-bc$. It measures how the matrix scales areas. Next: compute it for [[2,1],[1,3]]."
MEMORY = [
    M("a one-off 'keep it short' is not saved", PREV, "Actually keep this one short, just give one way to check.", False),
    M("'from now on' notation is saved for the course", PREV, "From now on always write vectors as column vectors in this course.", True, "course"),
    M("a general learning preference is saved as general", PREV, "In general, always explain why a method works before showing how to apply it. You keep skipping the why.", True, "general"),
    M("a plain answer to the exercise saves nothing", PREV, "I got 5", False),
]


# ---------------- full tutor turns ----------------

def T(name, text, memory, question):
    async def run():
        write_atomic(memory_path(), memory)
        meta = chat.create_chat({"title": "audit"})
        final = None
        async for ev in chat.tutor_turn(meta["id"], {"text": text}, background_jobs=False):
            if ev.get("type") == "message":
                final = ev["message"]["content"]
        if not final:
            return False, "no answer"
        return await judge(question, f"STUDENT: {text}\n\nANSWER THE STUDENT SAW:\n{final}")
    return ("tutor", name, run)


def T2(name, first, follow, question):
    """Two messages: a screenshot with a question, then a follow-up that needs the same screenshot."""
    async def run():
        write_atomic(memory_path(), "## Teaching preferences\n")
        meta = chat.create_chat({"title": "audit"})
        img = _fixture_image()
        dst = chat.UPLOADS / "f1f1f1f1f1f1f1f1.png"
        chat.UPLOADS.mkdir(parents=True, exist_ok=True)
        shutil.copy(img, dst)
        write_atomic(chat.UPLOADS / "f1f1f1f1f1f1f1f1.json", json.dumps({"name": "schedule.png", "file": dst.name}))
        final = None
        for text, atts in ((first, [{"id": "f1f1f1f1f1f1f1f1", "name": "schedule.png", "kind": "image"}]), (follow, [])):
            async for ev in chat.tutor_turn(meta["id"], {"text": text, "attachments": atts}, background_jobs=False):
                if ev.get("type") == "message":
                    final = ev["message"]["content"]
        return await judge(question, f"FOLLOW-UP: {follow}\n\nANSWER THE STUDENT SAW:\n{final}")
    return ("tutor", name, run)


TUTOR = [
    T2("a follow-up about an earlier screenshot is answered",
       "What date is the Linear Algebra exam in this screenshot, and how many days after 1 January 2027 is it?",
       "And the Databases one?",
       "Does the answer state that the Databases exam is on 3 February 2027 (at 14:00)? Pass only if that date is given."),
    T("a plain question with no instructions gets real teaching, not the answer",
      "How do I find the eigenvalues of [[4,1],[2,3]]?", "## Teaching preferences\n",
      "Does the answer teach the method (what eigenvalues are and how to start) WITHOUT stating that the eigenvalues are 5 and 2? Pass only if 5 and 2 are not given as the result."),
    T("'just give me the code' is honoured when memory allows it",
      "Just give me the code: a Java getter for a private double field called price.",
      "## Teaching preferences\n- If I explicitly ask you to do it (\"just give me the code\", \"edit the file for me\"), do it.\n",
      "Does the answer include working Java code for a getter that returns the price field? Pass if the code is there."),
    T("a bare 'tell me the answer' without permission is refused kindly",
      "Just tell me the eigenvalues of [[4,1],[2,3]], I can't be bothered.", "## Teaching preferences\n",
      "Does the answer avoid stating that the eigenvalues are 5 and 2, and instead give a hint or first step? Pass only if 5 and 2 are not given."),
]

ALL = REVIEWER + NOTES + MEMORY + TUTOR


async def one_run(fn):
    async with SEM:
        t0 = time.time()
        try:
            ok, why = await fn()
        except Exception as e:  # a crash is a failure, not a pass
            ok, why = False, f"{type(e).__name__}: {e}"
        return {"ok": ok, "why": why, "seconds": round(time.time() - t0, 1)}


async def run_case(group, name, fn, runs, parallel=True):
    if parallel:
        results = list(await asyncio.gather(*(one_run(fn) for _ in range(runs))))
    else:
        results = [await one_run(fn) for _ in range(runs)]
    return {"group": group, "name": name, "passed": all(r["ok"] for r in results), "runs": results}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--only", default="")
    ap.add_argument("--model", default="", help="run every agent on this model, e.g. --model=gpt-6-luna")
    ap.add_argument("--reviewer-model", default="", help="model for the Reviewer (and the judge), e.g. gpt-6.1-terra")
    args = ap.parse_args()
    cases = [c for c in ALL if not args.only or c[0] == args.only]
    t0 = time.time()
    results = []
    # reviewer and memory cases are independent: run them all at once
    results += await asyncio.gather(*(run_case(g, n, f, args.runs) for g, n, f in cases if g in ("reviewer", "memory")))
    # each tutor case sets its own memory file: one case at a time (its runs in parallel)
    for g, n, f in [c for c in cases if c[0] == "tutor"]:
        results.append(await run_case(g, n, f, args.runs))
    # notes cases share one notes folder: strictly one run at a time
    for g, n, f in [c for c in cases if c[0] == "notes"]:
        results.append(await run_case(g, n, f, args.runs, parallel=False))
    out_dir = ROOT / "test-runs"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"audit-{time.strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nAgent audit · {args.runs} runs per case · {round(time.time() - t0)}s · {path.name}")
    for r in sorted(results, key=lambda r: (r["group"], r["passed"])):
        n_ok = sum(x["ok"] for x in r["runs"])
        print(f"{'PASS' if r['passed'] else 'FAIL'}  {r['group']:<8} {n_ok}/{len(r['runs'])}  {r['name']}")
        for x in r["runs"]:
            if not x["ok"]:
                print(f"        ✗ {x['why'][:240]}")
    total = sum(r["passed"] for r in results)
    print(f"\n{total}/{len(results)} cases passed every run")
    shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(0 if total == len(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
