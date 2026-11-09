"""Linked Codex chats: continue a real Codex thread (from the Codex app, IDE or CLI) inside Scaffold.

Scaffold never copies the conversation. It reads the thread's history from Codex's own local databases
(~/.codex) and sends new turns with `codex exec resume <thread>`, so the same thread keeps its full context,
tools, AGENTS.md and settings, and the turns also appear in the Codex app.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import sqlite3
import time
from pathlib import Path

from .llm import LLMError, friendly_error

CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
TURN_TIMEOUT = 45 * 60
MAX_TURNS_SHOWN = 150
SCAFFOLD_MARK = "[Scaffold"  # every message Scaffold sends into a thread starts with this
IDE_REQUEST = re.compile(r"^# Context from my IDE setup:.*?## My request:\s*\n", re.S)


def _db(prefix: str) -> Path | None:
    """Codex keeps versioned databases (state_5.sqlite, thread_history_1.sqlite): use the newest."""
    found = sorted(CODEX_HOME.glob(f"{prefix}_*.sqlite"), key=lambda p: int(re.sub(r"\D", "", p.stem) or 0))
    return found[-1] if found else None


def _connect(prefix: str) -> sqlite3.Connection | None:
    p = _db(prefix)
    if not p:
        return None
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    return con


def available() -> bool:
    return bool(shutil.which("codex")) and _db("state") is not None


def _project_for(cwd: str, roots: list[tuple[str, str]]) -> str | None:
    best = None
    for name, root in roots:
        if cwd == root or cwd.startswith(root.rstrip("/") + "/"):
            if best is None or len(root) > len(best[1]):
                best = (name, root)
    return best[0] if best else None


def list_threads() -> list[dict]:
    """Every chat the user started in Codex (not archived, not Codex's own review sub-threads)."""
    con = _connect("state")
    if not con:
        return []
    with con:
        try:
            roots = [(r["name"], r["path"]) for r in con.execute(
                "select p.name, r.path from project_roots r join projects p on p.id = r.project_id")]
        except sqlite3.Error:
            roots = []
        rows = con.execute(
            "select id, coalesce(nullif(name, ''), title) as title, cwd, model, reasoning_effort, updated_at, "
            "tokens_used from threads where archived = 0 and coalesce(thread_source, 'user') = 'user' "
            "and coalesce(agent_role, '') = '' order by updated_at desc").fetchall()
    out = []
    for r in rows:
        title = " ".join((r["title"] or "").split())
        if not title or title.startswith("Guardian review") or title.startswith("The following is the Codex agent history"):
            continue
        out.append({"id": r["id"], "title": title[:120], "cwd": r["cwd"], "model": r["model"],
                    "effort": r["reasoning_effort"], "updated": r["updated_at"],
                    "project": _project_for(r["cwd"], roots) or Path(r["cwd"]).name})
    return out


def thread_info(tid: str) -> dict | None:
    con = _connect("state")
    if not con:
        return None
    with con:
        r = con.execute("select id, coalesce(nullif(name, ''), title) as title, cwd, model, reasoning_effort, "
                        "updated_at, rollout_path from threads where id = ?", (tid,)).fetchone()
    if not r:
        return None
    return {"id": r["id"], "title": " ".join((r["title"] or "").split())[:120], "cwd": r["cwd"], "model": r["model"],
            "effort": r["reasoning_effort"], "updated": r["updated_at"], "rollout_path": r["rollout_path"]}


def updated_times(tids: list[str]) -> dict[str, float]:
    if not tids:
        return {}
    con = _connect("state")
    if not con:
        return {}
    with con:
        q = f"select id, updated_at from threads where id in ({','.join('?' * len(tids))})"
        return {r["id"]: r["updated_at"] for r in con.execute(q, tids)}


def _history_ids(info: dict) -> list[str]:
    """A long thread's later turns are stored under a second id, which is in its rollout file name."""
    ids = [info["id"]]
    m = re.search(r"_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl", info.get("rollout_path") or "")
    if m:
        ids.append(m.group(1))
    return ids


def _item_text(item_json: str | None) -> str:
    if not item_json:
        return ""
    try:
        item = json.loads(item_json)
    except Exception:
        return ""
    if item.get("type") == "agentMessage":
        return item.get("text") or ""
    parts = [c.get("text", "") for c in item.get("content") or [] if c.get("type") == "text"]
    return "\n".join(p for p in parts if p)


def clean_user_text(text: str) -> str:
    """Show what the student typed, not the IDE context the Codex extension adds."""
    return IDE_REQUEST.sub("", text).strip()


def busy(tid: str) -> bool:
    """True if a turn is running in this thread right now (for example in the Codex app)."""
    info = thread_info(tid)
    con = _connect("thread_history")
    if not info or not con:
        return False
    ids = _history_ids(info)
    with con:
        r = con.execute(f"select status, started_at from thread_turns where thread_id in ({','.join('?' * len(ids))}) "
                        "order by started_at desc limit 1", ids).fetchone()
    import time
    return bool(r and r["status"] == "inProgress" and (r["started_at"] or 0) > time.time() - 3 * 3600)


def history(tid: str) -> list[dict]:
    """The thread's turns as chat messages: what the user wrote and Codex's final answer for each turn."""
    info = thread_info(tid)
    con = _connect("thread_history")
    if not info or not con:
        return []
    ids = _history_ids(info)
    with con:
        turns = con.execute(
            f"select turn_id, thread_id, status, started_at, first_user_item_id, final_agent_item_id from thread_turns "
            f"where thread_id in ({','.join('?' * len(ids))}) order by started_at, rollout_ordinal", ids).fetchall()
        turns = turns[-MAX_TURNS_SHOWN:]
        compacted = {(r["thread_id"], r["turn_id"]) for r in con.execute(
            f"select thread_id, turn_id from thread_items where thread_id in ({','.join('?' * len(ids))}) "
            "and item_type = 'contextCompaction'", ids)}
        out = []
        for t in turns:
            def item(iid):
                if not iid:
                    return None
                r = con.execute("select item_json from thread_items where thread_id = ? and item_id = ?",
                                (t["thread_id"], iid)).fetchone()
                return r["item_json"] if r else None
            user = _item_text(item(t["first_user_item_id"]))
            answer = _item_text(item(t["final_agent_item_id"]))
            ts = float(t["started_at"] or 0)
            if user:
                out.append({"role": "user", "content": user, "ts": ts, "source": "codex"})
            if (t["thread_id"], t["turn_id"]) in compacted:
                out.append({"role": "event", "kind": "compaction", "ts": ts + 0.25, "source": "codex",
                            "content": "Context compacted: Codex summarized the older part of this chat to make room."})
            if answer:
                out.append({"role": "assistant", "content": answer, "ts": ts + 0.5, "source": "codex"})
            elif t["status"] in ("failed", "interrupted") and user:
                out.append({"role": "assistant", "content": f"*(This turn was {t['status']} in Codex.)*", "ts": ts + 0.5,
                            "source": "codex"})
    return out


def context_usage(info: dict) -> dict | None:
    """How full the thread's context window is, from the last token count Codex recorded."""
    p = Path(info.get("rollout_path") or "")
    if not p.exists() or p.suffix != ".jsonl":
        return None
    try:
        with open(p, "rb") as f:
            f.seek(max(0, p.stat().st_size - 3_000_000))
            tail = f.read().decode(errors="replace")
    except OSError:
        return None
    for line in reversed(tail.splitlines()):
        if '"token_count"' not in line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        inf = (ev.get("payload") or {}).get("info") or {}
        last, window = inf.get("last_token_usage") or {}, inf.get("model_context_window")
        if last and window:
            used = (last.get("input_tokens") or 0) + (last.get("output_tokens") or 0)
            return {"used": used, "window": window}
    return None


class WriterBusy(LLMError):
    """The thread is open in another Codex process (the Codex app, VS Code), which holds its only write lock."""


async def run_turn_any(info: dict, prompt: str, images: list[str], model: str | None, effort: str | None):
    """Send a message into the thread, whoever holds it. Normally Scaffold runs the turn itself; if the chat is open
    in the Codex app or VS Code (which then owns the thread), the message is handed to that app and Scaffold reads
    the answer back from Codex's history."""
    try:
        async for ev in run_turn(info, prompt, images, model, effort):
            yield ev
        return
    except WriterBusy:
        pass
    yield ("event", {"kind": "tool", "text": "This chat is open in the Codex app, so Scaffold handed the message to it"})
    async for ev in run_turn_via_queue(info, prompt, images, model, effort):
        yield ev


async def run_turn_via_queue(info: dict, prompt: str, images: list[str], model: str | None, effort: str | None):
    """Deliver the message with `codex queue` to the process that holds the thread, then follow the turn in the
    history database until it finishes."""
    ids = _history_ids(info)
    sent = time.time()
    args = ["codex", "queue", "--thread", info["id"], "--message", prompt]
    if model:
        args += ["-m", model]
    if effort:
        args += ["-c", f'model_reasoning_effort="{effort}"']
    imgs = [p for p in images or [] if Path(p).exists()]
    if imgs:
        args += ["-i", *imgs]
    proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await asyncio.wait_for(proc.communicate(), 120)
    if proc.returncode != 0:
        raise LLMError("This chat is open in the Codex app and could not take the message. Close it there and try again. "
                       + (err or out).decode(errors="replace")[-200:])
    seen: set[str] = set()
    turn_key = None
    while time.time() - sent < TURN_TIMEOUT:
        await asyncio.sleep(1)
        yield ("tick", round(time.time() - sent))
        con = _connect("thread_history")
        if not con:
            continue
        with con:
            q = ",".join("?" * len(ids))
            if turn_key is None:
                r = con.execute(f"select thread_id, turn_id from thread_turns where thread_id in ({q}) and started_at >= ? "
                                "order by started_at desc limit 1", [*ids, int(sent) - 2]).fetchone()
                if not r:
                    continue
                turn_key = (r["thread_id"], r["turn_id"])
            items = con.execute("select item_id, item_type, item_json from thread_items where thread_id = ? and turn_id = ? "
                                "order by rollout_ordinal", turn_key).fetchall()
            turn = con.execute("select status, final_agent_item_id from thread_turns where thread_id = ? and turn_id = ?",
                               turn_key).fetchone()
        for it in items:
            if it["item_id"] in seen:
                continue
            seen.add(it["item_id"])
            try:
                data = json.loads(it["item_json"])
            except Exception:
                continue
            if it["item_type"] == "commandExecution":
                yield ("event", {"kind": "tool", "text": f"Ran `{_short_cmd(data.get('command', ''))}`"})
            elif it["item_type"] == "agentMessage" and data.get("phase") == "commentary":
                yield ("event", {"kind": "commentary", "text": data.get("text", "")})
            elif it["item_type"] == "contextCompaction":
                yield ("event", {"kind": "compaction", "text": "Context compacted: Codex summarized the older part of this chat to make room"})
        if turn and turn["status"] in ("completed", "failed", "interrupted"):
            final = ""
            if turn["final_agent_item_id"]:
                for it in items:
                    if it["item_id"] == turn["final_agent_item_id"]:
                        final = _item_text(it["item_json"])
            if not final:
                raise LLMError(f"The Codex app {turn['status']} this turn without an answer.")
            yield ("final", final.strip())
            return
    raise LLMError("The Codex app took longer than 45 minutes and Scaffold stopped waiting.")


ACTIVITY = {
    "command_execution": lambda it: f"Ran `{_short_cmd(it.get('command', ''))}`",
    "file_change": lambda it: "Edited " + ", ".join(Path(c.get("path", "")).name for c in it.get("changes") or []) or "Edited a file",
    "web_search": lambda it: f"Searched the web: {it.get('query', '')}",
    "mcp_tool_call": lambda it: f"Used {it.get('server', '')} · {it.get('tool', '')}",
}


def _short_cmd(cmd: str) -> str:
    cmd = re.sub(r"^/bin/(?:zsh|bash) -lc ", "", cmd).strip("'\"")
    return cmd if len(cmd) < 90 else cmd[:87] + "…"


async def run_turn(info: dict, prompt: str, images: list[str], model: str | None, effort: str | None):
    """Send one message into the thread. Yields ("event", dict) for live progress and finally ("final", text)."""
    if not shutil.which("codex"):
        raise LLMError("Codex CLI not found. Install it and run `codex login`.")
    cwd = info.get("cwd") if info.get("cwd") and Path(info["cwd"]).is_dir() else str(Path.home())
    args = ["codex", "exec", "resume", "--skip-git-repo-check", "--json"]
    if model:
        args += ["-m", model]
    imgs = [p for p in images or [] if Path(p).exists()]
    if imgs:
        args += ["-i", *imgs]
    args += ["-c", 'sandbox_mode="workspace-write"']  # a flag after -i ends the image list
    if effort:
        args += ["-c", f'model_reasoning_effort="{effort}"']
    args += [info["id"], "-"]
    proc = await asyncio.create_subprocess_exec(*args, cwd=cwd, stdin=asyncio.subprocess.PIPE,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                                limit=64 * 1024 * 1024)
    proc.stdin.write(prompt.encode())
    await proc.stdin.drain()
    proc.stdin.close()
    err_chunks: list[bytes] = []

    async def drain_err():
        while True:
            chunk = await proc.stderr.read(65536)
            if not chunk:
                break
            err_chunks.append(chunk)
    err_task = asyncio.create_task(drain_err())
    messages: list[str] = []
    failure = ""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + TURN_TIMEOUT
    start = loop.time()
    pending: asyncio.Task | None = None
    try:
        while True:
            if loop.time() > deadline:
                raise asyncio.TimeoutError
            if pending is None:
                pending = asyncio.ensure_future(proc.stdout.readline())
            done, _ = await asyncio.wait({pending}, timeout=1.0)
            if not done:
                yield ("tick", round(loop.time() - start))
                continue
            line = pending.result()
            pending = None
            if not line:
                break
            try:
                ev = json.loads(line)
            except Exception:
                continue
            kind = ev.get("type")
            item = ev.get("item") or {}
            itype = item.get("type")
            if kind == "item.completed" and itype == "agent_message":
                if messages:  # the previous message was commentary, not the answer
                    yield ("event", {"kind": "commentary", "text": messages[-1]})
                messages.append(item.get("text") or "")
            elif kind == "item.started" and itype in ACTIVITY:
                yield ("event", {"kind": "tool", "text": ACTIVITY[itype](item)})
            elif kind == "item.completed" and itype == "file_change":
                yield ("event", {"kind": "tool", "text": ACTIVITY["file_change"](item)})
            elif itype and "compact" in itype and kind == "item.completed":
                yield ("event", {"kind": "compaction", "text": "Context compacted: Codex summarized the older part of this chat to make room"})
            elif kind == "item.completed" and itype == "reasoning":
                yield ("event", {"kind": "thinking", "text": "Thinking"})
            elif kind == "turn.completed":
                from .llm import _record_usage
                _record_usage("codex-chat", model or info.get("model") or "", ev.get("usage"))
            elif kind in ("turn.failed", "error"):
                failure = (ev.get("error") or {}).get("message") or ev.get("message") or json.dumps(ev)[:300]
            elif kind == "item.completed" and itype == "error":
                msg = item.get("message") or ""
                if "recorded with model" not in msg:  # harmless warning when the model differs
                    yield ("event", {"kind": "warning", "text": msg[:200]})
    except asyncio.TimeoutError:
        proc.kill()
        raise LLMError("Codex took longer than 45 minutes and was stopped.")
    except (asyncio.CancelledError, GeneratorExit):
        if proc.returncode is None:
            proc.kill()
        raise
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
    code = await proc.wait()
    await err_task
    final = (messages[-1] if messages else "").strip()
    if not final:
        err = b"".join(err_chunks).decode(errors="replace")
        if "active writer" in err or "active writer" in failure:
            raise WriterBusy("This chat is open in another Codex window.")
        raise LLMError(friendly_error("codex", (failure or "") + "\n" + err[-4000:], model or "")
                       or f"Codex stopped without an answer (exit {code}).")
    yield ("final", final)


async def compact(tid: str, timeout: float = 600):
    """Ask Codex to compact the thread now (its own /compact), through the app-server protocol.
    Yields ("tick", seconds) while waiting; returns when Codex reports the thread was compacted."""
    if not shutil.which("codex"):
        raise LLMError("Codex CLI not found.")
    proc = await asyncio.create_subprocess_exec("codex", "app-server", stdin=asyncio.subprocess.PIPE,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                                                limit=64 * 1024 * 1024)

    async def send(msg: dict):
        proc.stdin.write((json.dumps(msg) + "\n").encode())
        await proc.stdin.drain()

    loop = asyncio.get_event_loop()
    start = loop.time()
    pending: asyncio.Task | None = None
    try:
        await send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "scaffold", "version": "1.0"}}})
        step = "init"
        while True:
            if loop.time() - start > timeout:
                raise LLMError("Codex did not finish compacting in time.")
            if pending is None:
                pending = asyncio.ensure_future(proc.stdout.readline())
            done, _ = await asyncio.wait({pending}, timeout=1.0)
            if not done:
                yield ("tick", round(loop.time() - start))
                continue
            line = pending.result()
            pending = None
            if not line:
                raise LLMError("Codex stopped before compacting.")
            try:
                msg = json.loads(line)
            except Exception:
                continue
            if msg.get("error"):
                detail = str(msg["error"].get("message") or msg["error"])
                if "active writer" in detail:
                    raise LLMError("This chat is open in the Codex app (or VS Code), which is holding it. "
                                   "Type /compact there, or close the chat there and try again.")
                raise LLMError("Codex could not compact: " + detail[:300])
            if msg.get("id") == 1 and step == "init":
                await send({"method": "initialized"})
                await send({"id": 2, "method": "thread/resume", "params": {"threadId": tid, "excludeTurns": True}})
                step = "resume"
            elif msg.get("id") == 2 and step == "resume":
                await send({"id": 3, "method": "thread/compact/start", "params": {"threadId": tid}})
                step = "compact"
            elif step == "compact" and msg.get("method") in ("thread/compacted", "turn/completed"):
                return
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
        if proc.returncode is None:
            proc.kill()
