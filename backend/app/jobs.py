"""Background jobs that survive dropped connections.

A long AI task (tutor answer, study plan) runs as an asyncio task on the server. Windows subscribe to its
event log and can reconnect at any time, resuming from the last event they saw. Closing the window,
sleeping the laptop or a network blip no longer kills the work.
"""
from __future__ import annotations

import asyncio
import json
import time
import traceback
import uuid
from typing import AsyncIterator, Callable

from . import llm

KEEP_FINISHED = 15 * 60  # seconds a finished job's log stays available


class Job:
    def __init__(self, key: str):
        self.key = key
        self.events: list[dict] = []
        self.done = False
        self.ok = False
        self.error: str | None = None
        self.started = time.time()
        self.tag = uuid.uuid4().hex[:8]  # tells a reconnecting client whether this is still the job it was following
        self.finished: float | None = None
        self.cond = asyncio.Condition()
        self.task: asyncio.Task | None = None

    async def push(self, ev: dict):
        async with self.cond:
            self.events.append(ev)
            self.cond.notify_all()


JOBS: dict[str, Job] = {}


def running(key: str) -> bool:
    j = JOBS.get(key)
    return bool(j and not j.done)


def any_running() -> list[str]:
    return [k for k, j in JOBS.items() if not j.done]


def _cleanup():
    now = time.time()
    for k in [k for k, j in JOBS.items() if j.done and j.finished and now - j.finished > KEEP_FINISHED]:
        JOBS.pop(k, None)


def cancel(key: str) -> bool:
    """Stop a running job (the model call is killed). Returns False if nothing was running."""
    j = JOBS.get(key)
    if not j or j.done or not j.task:
        return False
    j.task.cancel()
    return True


async def wait_done(key: str, timeout: float = 15):
    j = JOBS.get(key)
    if j and j.task and not j.done:
        try:
            await asyncio.wait_for(asyncio.shield(j.task), timeout)
        except BaseException:
            pass


async def push(key: str, ev: dict):
    """Add an event to a running job's log (e.g. 'a message was queued')."""
    j = JOBS.get(key)
    if j and not j.done:
        await j.push(ev)


def start(key: str, make: Callable[[], AsyncIterator[dict]], on_error: Callable[[str], None] | None = None,
          on_done: Callable[[bool], None] | None = None) -> Job:
    _cleanup()
    if running(key):
        raise RuntimeError("busy")
    job = Job(key)
    JOBS[key] = job

    async def run():
        try:
            async for ev in make():
                await job.push(ev)
            job.ok = True
        except llm.LLMError as e:
            job.error = str(e)
        except asyncio.CancelledError:
            job.error = "Stopped."
        except Exception as e:  # noqa
            traceback.print_exc()
            job.error = getattr(e, "user_message", None) or f"{type(e).__name__}: {e}"
        finally:
            if job.error:
                if on_error:
                    try:
                        on_error(job.error)
                    except Exception:
                        pass
                await job.push({"type": "error", "message": job.error})
            job.done = True
            job.finished = time.time()
            await job.push({"type": "end", "ok": job.ok, "stopped": job.error == "Stopped."})
            if on_done:
                try:
                    on_done(job.ok)
                except Exception:
                    traceback.print_exc()

    job.task = asyncio.create_task(run())
    return job


async def follow(key: str, after: int = 0, tag: str = ""):
    """SSE stream of a job's events after index `after`; ends when the job ends."""
    job = JOBS.get(key)
    if not job:
        yield "data: " + json.dumps({"type": "idle"}) + "\n\n"
        return
    i = max(0, after)
    if (tag and tag != job.tag) or i > len(job.events):
        i = 0  # the index is from an earlier job with this key: replay this one from the start
    while True:
        async with job.cond:
            try:
                await asyncio.wait_for(job.cond.wait_for(lambda: len(job.events) > i), timeout=15)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue
        while i < len(job.events):
            ev = job.events[i]
            i += 1
            # skip stale heartbeats when replaying a long backlog
            if ev.get("type") == "status" and ev.get("heartbeat") and i < len(job.events) - 1:
                continue
            yield f"id: {job.tag}:{i}\ndata: {json.dumps(ev)}\n\n"
            if ev.get("type") == "end":
                return
