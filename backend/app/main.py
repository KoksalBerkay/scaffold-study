"""FastAPI app: settings, materials, planner, notes, chats."""
from __future__ import annotations

import json
import os
import shutil
import traceback
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from . import llm, materials, planner
from .config import (PROMPT_NAMES, ROOT, WORKSPACE, default_prompt, get_memory, get_prompt,
                     load_settings, memory_path, notes_dir, prompt_path, save_settings)
from .files import note_target, notes_tree

app = FastAPI(title="Scaffold")


@app.exception_handler(ValueError)
async def value_error(_request: Request, exc: ValueError):
    """Bad input (e.g. a path outside the notes folder) is a 400, not a crash."""
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=400, content={"detail": str(exc)})


def sse(gen):
    async def stream():
        try:
            async for ev in gen:
                yield f"data: {json.dumps(ev)}\n\n"
        except llm.LLMError as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        except Exception as e:  # noqa
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': f'{type(e).__name__}: {e}'})}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------- settings & models ----------------

def _mask(key: str) -> str:
    return (key[:3] + "…" + key[-4:]) if key and len(key) > 10 else ("•••" if key else "")


@app.get("/api/settings")
def get_settings():
    s = load_settings()
    for p in ("openai", "anthropic"):
        s["providers"][p]["api_key"] = _mask(s["providers"][p].get("api_key", ""))
    s["notes_path_effective"] = str(notes_dir())
    return s


@app.put("/api/settings")
def put_settings(body: dict = Body(...)):
    cur = load_settings()
    for p in ("openai", "anthropic"):
        new = (body.get("providers") or {}).get(p, {}).get("api_key")
        if new is None or "…" in new or new == "•••":
            body.setdefault("providers", {}).setdefault(p, {})["api_key"] = cur["providers"][p].get("api_key", "")
    body.pop("notes_path_effective", None)
    save_settings({**cur, **body})
    return get_settings()


@app.get("/api/models")
async def models():
    return {"catalog": await llm.model_catalog()}


@app.post("/api/models/test")
async def test_model(body: dict = Body(...)):
    role = body.get("role", "tutor")
    try:
        out = await llm.complete(role, "You are a connection test. Reply with exactly: ready",
                                 [{"role": "user", "content": "ping"}])
        return {"ok": True, "reply": out[:200]}
    except llm.LLMError as e:
        return {"ok": False, "reply": str(e)}


@app.get("/api/version")
def version():
    """Changes whenever the frontend is rebuilt, so open windows can reload themselves."""
    idx = ROOT / "frontend" / "dist" / "index.html"
    return {"build": idx.stat().st_mtime if idx.exists() else 0}


# ---------------- prompts & memory ----------------

@app.get("/api/prompts")
def list_prompts():
    return [{"name": n, "content": get_prompt(n), "customized": prompt_path(n).exists()} for n in PROMPT_NAMES]


@app.put("/api/prompts/{name}")
def put_prompt(name: str, body: dict = Body(...)):
    if name not in PROMPT_NAMES:
        raise HTTPException(404)
    p = prompt_path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body["content"])
    return {"ok": True}


@app.delete("/api/prompts/{name}")
def reset_prompt(name: str):
    p = prompt_path(name)
    if p.exists():
        p.unlink()
    return {"content": default_prompt(name)}


@app.get("/api/memory")
def read_memory():
    return {"content": get_memory()}


@app.put("/api/memory")
def write_memory(body: dict = Body(...)):
    memory_path().parent.mkdir(parents=True, exist_ok=True)
    memory_path().write_text(body["content"])
    return {"ok": True}


# ---------------- filesystem & materials ----------------

@app.get("/api/fs/browse")
def browse(path: str = ""):
    p = Path(path).expanduser() if path else Path.home()
    if not p.is_dir():
        raise HTTPException(400, "Not a folder")
    dirs = []
    try:
        for c in sorted(p.iterdir(), key=lambda x: x.name.lower()):
            if c.is_dir() and not c.name.startswith("."):
                dirs.append({"name": c.name, "path": str(c)})
    except PermissionError:
        pass
    shortcuts = [{"name": n, "path": str(Path.home() / n)} for n in ("Desktop", "Documents", "Downloads")
                 if (Path.home() / n).is_dir()]
    demo = ROOT / "demo-materials"
    if demo.is_dir():
        shortcuts.insert(0, {"name": "Demo materials", "path": str(demo)})
    return {"path": str(p), "parent": str(p.parent) if p.parent != p else None, "dirs": dirs,
            "shortcuts": shortcuts}


@app.post("/api/materials/scan")
def scan(body: dict = Body(...)):
    p = Path(body["path"]).expanduser()
    if not p.is_dir():
        raise HTTPException(400, "That folder does not exist")
    s = load_settings()
    s["materials_path"] = str(p)
    save_settings(s)
    courses = materials.scan(p)
    return {"path": str(p), "courses": [
        {"name": c["name"], "counts": c["counts"], "n_files": len(c["files"]),
         "files": [{k: f[k] for k in ("rel", "name", "kind", "pages", "date")} for f in c["files"]]}
        for c in courses]}


@app.get("/api/materials/raw")
def raw_material(path: str):
    root = Path(load_settings().get("materials_path") or "/").expanduser()
    try:
        p = materials.safe_path(root, path)
    except ValueError:
        raise HTTPException(403, "Outside the materials folder")
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


# ---------------- planner ----------------

@app.get("/api/planner")
def planner_state():
    from . import jobs
    return {"setup": planner.load_setup(), "files": planner.read_plan(), "plan_dir": planner.PLAN_DIR,
            "running": jobs.running("planner")}


def _start_planner(make):
    from . import jobs
    if jobs.running("planner"):
        raise HTTPException(409, "The planner is already working. Wait for it to finish.")
    jobs.start("planner", make)
    return {"ok": True}


@app.post("/api/planner/generate")
async def planner_generate(body: dict = Body(...)):
    if not body.get("materials_path") or not Path(body["materials_path"]).expanduser().is_dir():
        raise HTTPException(400, "Choose an existing materials folder first.")
    return _start_planner(lambda: planner.generate(body))


@app.post("/api/planner/log")
async def planner_log(body: dict = Body(...)):
    if not (body.get("text") or "").strip():
        raise HTTPException(400, "Write what you did first.")
    return _start_planner(lambda: planner.log_progress(body["text"]))


@app.get("/api/planner/events")
async def planner_events(after: int = 0):
    from . import jobs
    return StreamingResponse(jobs.follow("planner", after), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/planchat")
def planchat_info():
    from . import planchat
    meta = planchat.ensure_plan_chat()
    return {"id": meta["id"]}


@app.post("/api/planner/toggle")
def planner_toggle(body: dict = Body(...)):
    try:
        content = planner.toggle(int(body["line"]), bool(body["checked"]), body.get("file", "Quick Plan"), body.get("text"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"content": content}


# ---------------- notes ----------------

@app.get("/api/notes")
def notes_list():
    return {"root": str(notes_dir()), "notes": notes_tree()}


@app.get("/api/notes/file")
def note_read(path: str):
    p = note_target(path)
    if not p.exists():
        raise HTTPException(404)
    return {"path": path, "content": p.read_text()}


@app.put("/api/notes/file")
def note_write(body: dict = Body(...)):
    p = note_target(body["path"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body["content"])
    return {"ok": True}


# ---------------- chats (added in chat.py) ----------------
try:
    from .chat import router as chat_router  # noqa: E402
    app.include_router(chat_router)
except ImportError:
    pass


# ---------------- frontend ----------------
DIST = ROOT / "frontend" / "dist"
UPDATING_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Scaffold</title>
<meta http-equiv="refresh" content="2"><style>body{margin:0;height:100vh;display:grid;place-items:center;
background:#0e1015;color:#8b93a3;font:15px Inter,system-ui,sans-serif}</style></head>
<body><div>Scaffold is updating… this page reloads by itself.</div></body></html>"""


@app.get("/assets/{name:path}")
def asset(name: str):
    f = (DIST / "assets" / name).resolve()
    if (DIST / "assets").resolve() not in f.parents or not f.is_file():
        raise HTTPException(404)
    return FileResponse(f, headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.get("/{full_path:path}")
def spa(full_path: str):
    from fastapi.responses import HTMLResponse
    if full_path.startswith("api/"):
        raise HTTPException(404, "Unknown API route")
    f = DIST / full_path
    if full_path and f.is_file() and f.name != "index.html":
        return FileResponse(f)
    index = DIST / "index.html"
    if not index.is_file():  # mid-build or not built yet: never show an error page that can't recover
        return HTMLResponse(UPDATING_PAGE, headers={"Cache-Control": "no-store"})
    # never cache the page itself: after a rebuild every window must get the new asset names
    return FileResponse(index, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
