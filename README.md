<div align="center">

# 🎓 Scaffold

**An agentic study app that plans your semester, teaches you from your own materials, and never just hands you the answer.**

*Built for Clash Reply · Student Tech Clash 2026: AI on Campus*

`Planner` → `Tutor` ⇄ `Reviewer` → `Notes` + `Memory`

</div>

---

## ✨ What it does

| | |
| --- | --- |
| 🗓️ **Study planner** | Point it at your materials folder, add exam dates and hours. The Planner reads every past exam, question by question, and writes **Quick Plan**, **Study Plan**, **Time Estimates** and **Context** as markdown files you keep. |
| ⏱️ **Real time estimates** | Minutes come from the material itself (points, exam length, question type, how new the topic is), not "90 min per block". Logging progress recalibrates them. |
| ✅ **Trackable** | This week is a checklist. Tick tasks, hit **Study this** to open a tutor chat on that exact exercise, and **Log progress** to reschedule. |
| 🧑‍🏫 **Tutor** | Teaches from zero, anchored to a real exercise. Guides you step by step. Doesn't solve it for you. |
| 🔍 **Reviewer** | A second agent checks every tutor reply for correctness, completeness and answer-giving *before* you see it. |
| 🧠 **Personal memory** | Criticise the teaching ("you skipped why this works") and it becomes a lasting rule for **you**. |
| 📝 **Auto-notes** | Clean, exam-ready notes in the right course folder. Obsidian-compatible, with LaTeX math. |
| ✍️ **Live-preview editor** | Edit notes like in Obsidian: formatting, math, tables, callouts, properties and tags render in place, and raw markdown appears only on the line you're editing. Autosaves. |
| 🔌 **Any model** | ChatGPT subscription (Codex CLI), Claude subscription (Claude Code CLI), OpenAI API key, Anthropic API key. Pick a model per agent in the UI. |
| 🎛️ **You're in control** | Every system prompt and the memory are editable in Settings. |

## 🚀 How to run

```bash
./run.sh
```

Then open **http://127.0.0.1:8765**.

The script creates the Python env, installs the frontend packages, builds the UI, generates a small `demo-materials/` folder, and starts the server.

**You need:** Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+, and at least one model provider:

- **ChatGPT subscription:** install the Codex CLI and run `codex login` *(default and used for the demo)*
- **Claude subscription:** install Claude Code and log in
- **API keys:** paste an OpenAI or Anthropic key in **Settings → Models**

<details>
<summary><b>Development mode (hot reload)</b></summary>

```bash
# terminal 1: backend
cd backend && .venv/bin/python -m uvicorn app.main:app --port 8765 --reload --timeout-graceful-shutdown 2
# terminal 2: frontend on http://localhost:5173 (proxies /api to the backend)
cd frontend && npm run dev
```
</details>

## 🧭 Architecture

```
frontend/  React + Vite · KaTeX math · dark/light theme
backend/   FastAPI · PyMuPDF (PDF text + page images)
  app/llm.py        one interface for every provider: complete(system, messages, images) → text
  app/planner.py    setup → inventory → Planner → 4 plan files; log progress → Plan updater
  app/materials.py  scan, classify (exam / solution / slides / exercises), search, render pages
  app/prompts/      default prompts (overridable in Settings)
workspace/          your data, local only: settings, memory, notes, chats, prompt overrides
```

Everything stays on your computer. Notes are plain `.md`, so you can point the notes folder at an Obsidian vault.

## 🗂️ What the planner writes

```
notes/Study Plan/
  Quick Plan.md      this week as a checklist: file link · question range · ~minutes
  Study Plan.md      weekly hours per course, assignments by week, coverage, mock exams
  Time Estimates.md  exam anchors, per-question estimates with reasons, does-it-fit, calibration
  Context.md         material inventory, exam rules, preferences, unknowns, dated updates
```
