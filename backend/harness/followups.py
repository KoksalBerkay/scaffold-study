"""Follow-up test: does the Reviewer make the Tutor teach properly without giving the answer away?

Each scenario is a scripted student conversation (start → demand the answer → wrong attempt → critique →
correct answer). It runs through the real Tutor pipeline twice, with the Reviewer OFF and ON, and a judge
agent grades every tutor reply. Writes a JSON file and a markdown report into the notes folder.

    cd backend && .venv/bin/python -m harness.followups            # all scenarios
    cd backend && .venv/bin/python -m harness.followups eigenvalues
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import sys
from pathlib import Path

from app import chat, llm
from app.config import WORKSPACE, load_settings, save_settings
from app.files import write_note

HERE = Path(__file__).parent
ROOT = HERE.parents[1]

EXPECT = {
    "start": "Teach the prerequisites from zero, anchored to the exercise. Must NOT give the final answer or do the student's next step. End with one clear step for the student.",
    "demand_answer": "The student asks for the answer without having tried. Must NOT give it. Must keep guiding with a smaller step or a hint.",
    "wrong_attempt": "Must find the FIRST wrong step (see FIRST ERROR) and explain why it is wrong, without fixing the later steps or giving the final answer.",
    "critique": "The student says something was skipped. Must explain exactly that, from zero, then return to the exercise.",
    "correct": "The student produced the right result. Must confirm it plainly and move to the next part. Repeating the student's own result is fine.",
}

JUDGE = """You grade one reply of an AI tutor in a study app. Be strict and honest.

EXERCISE: {exercise}
ANSWER THE TUTOR MUST NOT REVEAL BEFORE THE STUDENT REACHES IT: {secret}
WHAT THIS REPLY MUST DO: {expect}
{first_error}
STUDENT MESSAGE: {student}

TUTOR REPLY:
{reply}

Reply with JSON only:
{{"gave_answer_early": true | false,
  "taught_prerequisites": 1-5,
  "found_first_error": true | false | null,
  "one_clear_next_step": true | false,
  "met_expectation": true | false,
  "comment": "one sentence"}}
Rules: gave_answer_early is true if the reply states the final answer, the full solution, or performs the step the student should do next (ignore this for kind "correct"). found_first_error is null unless the student sent an attempt. taught_prerequisites: 5 = a zero-knowledge student can follow every step."""


async def run_conversation(sc: dict, review: bool) -> list[dict]:
    meta = chat.create_chat({"title": f"[harness] {sc['id']} review={review}", "harness": True,
                             "pinned_files": [str((Path(load_settings()["materials_path"]) / sc["file"]).as_uri())]})
    turns = []
    for step in sc["steps"]:
        msg, reviews = None, []
        async for ev in chat.tutor_turn(meta["id"], {"text": step["text"]}, review=review, background_jobs=False):
            if ev.get("type") == "message":
                msg = ev["message"]
            if ev.get("type") == "review":
                reviews.append(ev)
        turns.append({"step": step, "reply": msg["content"] if msg else "", "review": (msg or {}).get("review")})
        print(f"  {sc['id']:14} review={'on ' if review else 'off'} {step['kind']:14} done", flush=True)
    return turns


async def judge(sc: dict, turn: dict) -> dict:
    step = turn["step"]
    prompt = JUDGE.format(exercise=sc["exercise"], secret=sc["secret"], expect=EXPECT[step["kind"]],
                          first_error=f"FIRST ERROR IN THE ATTEMPT: {step['first_error']}" if step.get("first_error") else "",
                          student=step["text"], reply=turn["reply"])
    out = await llm.complete("reviewer", "You are a strict, fair grader. JSON only.", [{"role": "user", "content": prompt}])
    data = chat.parse_json(out) or {}
    if step["kind"] == "correct":
        data["gave_answer_early"] = False
    if step["kind"] != "wrong_attempt":
        data["found_first_error"] = None  # only meaningful when the student sent an attempt
    return data


def pct(xs):
    xs = [x for x in xs if x is not None]
    return f"{round(100 * sum(1 for x in xs if x) / len(xs))}%" if xs else "–"


def avg(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return f"{sum(xs) / len(xs):.1f}" if xs else "–"


def report(results: list[dict]) -> str:
    rows = {True: [], False: []}
    for r in results:
        rows[r["review"]] += r["grades"]
    def line(label, key, fn, invert=False):
        on, off = fn([g.get(key) for g in rows[True]]), fn([g.get(key) for g in rows[False]])
        return f"| {label} | {off} | **{on}** |"
    early = lambda xs: pct(xs)  # noqa: E731
    lines = [
        "---", "tags:", "  - evaluation", f"updated: {dt.date.today().isoformat()}", "---",
        "# Reviewer follow-up test",
        "Scripted student conversations run through the real app: start from zero, demand the answer, send a wrong attempt, criticise a skipped step, then give the right answer. Every tutor reply is graded by a separate judge agent.",
        "",
        "| Check | Tutor alone | Tutor + Reviewer |", "| --- | ---: | ---: |",
        line("Gave the answer too early (lower is better)", "gave_answer_early", early),
        line("Met the expectation for that step", "met_expectation", pct),
        line("Found the first wrong step in an attempt", "found_first_error", pct),
        line("Ended with one clear next step", "one_clear_next_step", pct),
        line("Prerequisites taught (1–5)", "taught_prerequisites", avg),
        "",
        f"{len(results) // 2} scenarios × {len(results[0]['grades']) if results else 0} follow-ups, each run with the Reviewer off and on. "
        "Small sample from a single run: read it as a direction, not a precise measurement.",
        "",
    ]
    catches = []
    for r in results:
        if not r["review"]:
            continue
        for t in r["turns"]:
            for rd in (t["review"] or {}).get("rounds", []):
                for iss in rd.get("issues", []):
                    catches.append((r["scenario"], t["step"]["kind"], iss))
    if catches:
        lines += ["## What the Reviewer caught", "| Scenario | Step | Issue | Fix the Tutor had to make |", "| --- | --- | --- | --- |"]
        for scn, kind, iss in catches[:15]:
            fix = str(iss.get("fix", "")).replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {scn} | {kind} | {iss.get('type')} | {fix} |")
        lines.append("")
    lines.append("## Per step")
    for r in results:
        lines.append(f"### {r['scenario']} · Reviewer {'on' if r['review'] else 'off'}")
        lines += ["| Step | Early answer | First error | Next step | Prereqs | Judge |", "| --- | --- | --- | --- | --- | --- |"]
        for t, g in zip(r["turns"], r["grades"]):
            yn = lambda v: "–" if v is None else ("yes" if v else "no")  # noqa: E731
            lines.append(f"| {t['step']['kind']} | {yn(g.get('gave_answer_early'))} | {yn(g.get('found_first_error'))} | "
                         f"{yn(g.get('one_clear_next_step'))} | {g.get('taught_prerequisites', '–')} | {str(g.get('comment', '')).replace('|', '/')} |")
        lines.append("")
    return "\n".join(lines)


async def main():
    s = load_settings()
    if not s.get("materials_path"):
        s["materials_path"] = str(ROOT / "demo-materials")
        save_settings(s)
    scenarios = json.loads((HERE / "scenarios.json").read_text())
    if sys.argv[1:]:
        scenarios = [x for x in scenarios if x["id"] in sys.argv[1:]]
    jobs = [(sc, rv) for sc in scenarios for rv in (False, True)]
    convos = await asyncio.gather(*(run_conversation(sc, rv) for sc, rv in jobs))
    results = []
    for (sc, rv), turns in zip(jobs, convos):
        grades = await asyncio.gather(*(judge(sc, t) for t in turns))
        results.append({"scenario": sc["id"], "review": rv, "turns": turns, "grades": grades})
    out = WORKSPACE / "harness"
    out.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    (out / f"followups-{stamp}.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
    write_note("Evaluation/Reviewer Follow-up Test.md", report(results))
    print("\nReport: notes/Evaluation/Reviewer Follow-up Test.md")


def rebuild(json_path: str, note: str):
    """Regenerate a report from a saved run (applies the current scoring rules)."""
    results = json.loads(Path(json_path).read_text())
    for r in results:
        for t, g in zip(r["turns"], r["grades"]):
            if t["step"]["kind"] != "wrong_attempt":
                g["found_first_error"] = None
            if t["step"]["kind"] == "correct":
                g["gave_answer_early"] = False
    write_note(note, report(results))


if __name__ == "__main__":
    if sys.argv[1:2] == ["--rebuild"]:
        rebuild(sys.argv[2], sys.argv[3])
    else:
        asyncio.run(main())
