"""Cached Codex calls for Scaffold's own agents (Tutor, Reviewer, Notes, memory, summary, Planner).

A one-off `codex exec` call is a new session every time, and Codex gives every session its own prompt-cache key, so
nothing is ever reused: each call pays for its whole prompt. Here every agent setup (model + instructions) gets a
long-lived *worker thread* instead. A job is one turn in that thread; afterwards the turn is reverted, so the thread
never grows and the next job starts from the same, already-cached prefix (measured: ~98% of the prompt cached).

Worker threads are archived between jobs, so they never show up in the Codex app's chat list. If anything about the
pool fails, the caller falls back to a plain `codex exec` call, so answers never depend on it.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import time
from pathlib import Path

from .config import WORKSPACE, read_json, write_atomic

POOL_FILE = WORKSPACE / "cache" / "codex-pool.json"
KEEP_SETUPS = 24          # remember worker threads for this many recent agent setups
KEEP_IDLE_PER_SETUP = 3   # idle threads kept per setup (more are created when jobs run in parallel)


class PoolError(Exception):
    pass


class CodexPool:
    def __init__(self):
        self.proc: asyncio.subprocess.Process | None = None
        self.reader: asyncio.Task | None = None
        self.pending: dict[int, asyncio.Future] = {}
        self.thread_events: dict[str, asyncio.Queue] = {}
        self.next_id = 0
        self.write_lock = asyncio.Lock()
        self.start_lock = asyncio.Lock()
        self.idle: dict[str, list[str]] = {}
        self.loaded = False

    # ---------- process ----------
    async def _ensure(self, features_off: list[str], run_dir: Path):
        if self.proc and self.proc.returncode is None:
            return
        async with self.start_lock:
            if self.proc and self.proc.returncode is None:
                return
            if not shutil.which("codex"):
                raise PoolError("codex not installed")
            args = ["codex", "app-server"]
            for f in features_off:
                args += ["-c", f"features.{f}=false"]
            self.proc = await asyncio.create_subprocess_exec(
                *args, cwd=str(run_dir), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL, limit=64 * 1024 * 1024)
            self.pending.clear()
            self.reader = asyncio.create_task(self._read())
            try:
                await self._request("initialize", {"clientInfo": {"name": "scaffold", "version": "1.0"}}, timeout=30)
                await self._send({"method": "initialized"})
            except BaseException:
                # never keep a server that did not finish starting: the next job starts a fresh one
                if self.proc.returncode is None:
                    self.proc.kill()
                raise
            await self._archive_strays()
            if not self.loaded:
                data = read_json(POOL_FILE, {}) or {}
                self.idle = {k: list(v.get("threads", [])) for k, v in data.items() if isinstance(v, dict)}
                self.loaded = True

    async def _archive_strays(self):
        """A job interrupted mid-way (app closed, server stopped) can leave its worker thread unarchived, which
        would show it in the Codex app. Archive any such leftovers when the pool starts."""
        try:
            from .codexlink import _connect
            con = _connect("state")
            if not con:
                return
            with con:
                ids = [r["id"] for r in con.execute(
                    "select id from threads where archived = 0 and thread_source = 'scaffold_worker'")]
            for tid in ids:
                try:
                    await self._request("thread/archive", {"threadId": tid}, timeout=15)
                except Exception:
                    pass
        except Exception:
            pass

    async def _read(self):
        proc = self.proc
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                try:
                    msg = json.loads(line)
                except Exception:
                    continue
                if "id" in msg and ("result" in msg or "error" in msg):
                    fut = self.pending.pop(msg["id"], None)
                    if fut and not fut.done():
                        fut.set_result(msg)
                    continue
                params = msg.get("params") or {}
                tid = params.get("threadId") or (params.get("thread") or {}).get("id")
                if tid and tid in self.thread_events:
                    self.thread_events[tid].put_nowait(msg)
        finally:
            for fut in self.pending.values():
                if not fut.done():
                    fut.set_exception(PoolError("Codex app-server stopped"))
            self.pending.clear()
            for q in self.thread_events.values():
                q.put_nowait({"method": "__closed__"})

    async def _send(self, msg: dict):
        async with self.write_lock:
            self.proc.stdin.write((json.dumps(msg) + "\n").encode())
            await self.proc.stdin.drain()

    async def _request(self, method: str, params: dict, timeout: float = 60):
        self.next_id += 1
        i = self.next_id
        fut = asyncio.get_event_loop().create_future()
        self.pending[i] = fut
        await self._send({"id": i, "method": method, "params": params})
        msg = await asyncio.wait_for(fut, timeout)
        if "error" in msg:
            raise PoolError(f"{method}: {msg['error'].get('message') if isinstance(msg['error'], dict) else msg['error']}")
        return msg.get("result") or {}

    # ---------- worker threads ----------
    def _save(self, key: str):
        data = read_json(POOL_FILE, {}) or {}
        data[key] = {"threads": self.idle.get(key, [])[:KEEP_IDLE_PER_SETUP], "used": time.time()}
        if len(data) > KEEP_SETUPS:  # forget the oldest setups (their archived threads stay hidden)
            for k in sorted(data, key=lambda k: data[k].get("used", 0))[:len(data) - KEEP_SETUPS]:
                data.pop(k, None)
                self.idle.pop(k, None)
        write_atomic(POOL_FILE, json.dumps(data, indent=2))

    async def _new_thread(self, model: str, base: str, instructions: str, run_dir: Path, role: str) -> str:
        r = await self._request("thread/start", {
            "model": model, "cwd": str(run_dir), "sandbox": "read-only", "approvalPolicy": "never",
            "baseInstructions": base, "developerInstructions": instructions, "threadSource": "scaffold_worker"})
        tid = r["thread"]["id"]
        try:
            await self._request("thread/name/set", {"threadId": tid, "name": f"Scaffold worker · {role}"})
        except PoolError:
            pass
        return tid

    async def run(self, *, model: str, effort: str | None, base: str, instructions: str, text: str,
                  images: list[str], run_dir: Path, features_off: list[str], role: str, timeout: float):
        """One job. Returns (final_text, usage dict or None)."""
        await self._ensure(features_off, run_dir)
        key = hashlib.sha1(f"{model}\n{base}\n{instructions}".encode()).hexdigest()[:16]
        pool = self.idle.setdefault(key, [])
        tid = pool.pop() if pool else None
        fresh = tid is None
        if fresh:
            tid = await self._new_thread(model, base, instructions, run_dir, role)
        q: asyncio.Queue = asyncio.Queue()
        self.thread_events[tid] = q
        turn_id = None
        turn_over = False
        ok = False
        try:
            if not fresh:
                await self._request("thread/unarchive", {"threadId": tid})
                # instructions are not restored by resume on their own: pass them again (same text, so still cached)
                await self._request("thread/resume", {"threadId": tid, "excludeTurns": True, "model": model,
                                                      "baseInstructions": base, "developerInstructions": instructions,
                                                      "sandbox": "read-only", "approvalPolicy": "never", "cwd": str(run_dir)})
            items = [{"type": "text", "text": text}] + [{"type": "localImage", "path": p} for p in images]
            params = {"threadId": tid, "input": items}
            if effort:
                params["effort"] = effort
            r = await self._request("turn/start", params)
            turn_id = r["turn"]["id"]
            final, usage, failure = "", None, ""
            deadline = time.time() + timeout
            while True:
                if time.time() >= deadline:  # checked here too: a steady stream of events must not postpone it forever
                    raise asyncio.TimeoutError()
                msg = await asyncio.wait_for(q.get(), max(1, deadline - time.time()))
                m = msg.get("method", "")
                p = msg.get("params") or {}
                if m == "__closed__":
                    raise PoolError("Codex app-server stopped during the job")
                if m == "item/completed" and (p.get("item") or {}).get("type") == "agentMessage":
                    final = p["item"].get("text") or final
                elif m == "thread/tokenUsage/updated":
                    usage = (p.get("tokenUsage") or {}).get("last") or usage
                elif m == "error":
                    failure = json.dumps(p)[:500]
                elif m == "turn/completed":
                    turn = p.get("turn") or {}
                    if turn.get("status") not in (None, "completed"):
                        failure = failure or json.dumps(turn.get("error") or turn)[:500]
                    turn_over = True
                    break
            if failure and not final:
                raise PoolError(failure)
            ok = True
            return final, usage
        finally:
            try:
                if turn_id and not turn_over:
                    # stopped or timed out: tell Codex to stop too, or the turn keeps running (and costing) unseen
                    await self._request("turn/interrupt", {"threadId": tid, "turnId": turn_id}, timeout=10)
                    end = time.time() + 10
                    while time.time() < end:
                        msg = await asyncio.wait_for(q.get(), max(0.1, end - time.time()))
                        if msg.get("method") in ("turn/completed", "__closed__"):
                            break
            except Exception:
                pass
            self.thread_events.pop(tid, None)
            try:
                if turn_id:
                    await self._request("thread/revert", {"threadId": tid, "beforeTurnId": turn_id})
                await self._request("thread/archive", {"threadId": tid})
                if ok:
                    self.idle.setdefault(key, []).append(tid)
                    self._save(key)
            except Exception:
                pass  # a broken worker is simply not reused


POOL = CodexPool()
