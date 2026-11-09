"""One interface for every provider: complete(role, system, messages) -> text.

messages: [{"role": "user" | "assistant", "content": str, "images": [abs paths]}]

Providers:
  openai       OpenAI API key (chat completions)
  anthropic    Anthropic API key (messages API)
  codex        ChatGPT subscription through the Codex CLI (`codex exec`)
  claude_code  Claude subscription through the Claude Code CLI (`claude -p`)
"""
from __future__ import annotations

import asyncio
import base64
import contextvars
import json
import mimetypes
import shutil
import tempfile
from pathlib import Path

import httpx

from .config import WORKSPACE, load_settings

PROVIDERS = {
    "codex": "ChatGPT subscription (Codex CLI)",
    "claude_code": "Claude subscription (Claude Code CLI)",
    "openai": "OpenAI API key",
    "anthropic": "Anthropic API key",
}

MODEL_SUGGESTIONS = {
    "codex": ["gpt-6.1-sol", "gpt-6-astra"],
    "claude_code": ["opus", "sonnet", "haiku"],
    "openai": ["gpt-6.1-sol", "gpt-6-astra"],
    "anthropic": ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"],
}

EFFORTS = ["low", "medium", "high"]


def codex_models() -> list[dict]:
    """Models the user's ChatGPT subscription can use, read from the Codex CLI's own cache."""
    for f in sorted(Path.home().glob(".codex/*models*.json")):
        try:
            d = json.loads(f.read_text())
            ms = d.get("models", d) if isinstance(d, dict) else d
            out = []
            for m in sorted(ms, key=lambda m: m.get("priority", 99)):
                slug = m.get("slug") or m.get("id")
                if not slug or "review" in slug or m.get("visibility") not in (None, "list"):
                    continue
                levels = m.get("supported_reasoning_levels") or []
                out.append({
                    "id": slug, "label": m.get("display_name") or slug, "description": m.get("description") or "",
                    "vision": "image" in (m.get("input_modalities") or ["image"]),
                    "efforts": [e.get("effort") for e in levels if e.get("effort")],
                    "effort_help": {e.get("effort"): e.get("description", "") for e in levels},
                    "default_effort": m.get("default_reasoning_level") or "medium",
                })
            if out:
                return out
        except Exception:
            continue
    return []


CLAUDE_CODE_MODELS = [
    {"id": "opus", "label": "Opus (latest)", "description": "Most capable. Best for teaching and planning.", "vision": True},
    {"id": "sonnet", "label": "Sonnet (latest)", "description": "Fast and strong. Good default.", "vision": True},
    {"id": "haiku", "label": "Haiku (latest)", "description": "Fastest. Fine for background work.", "vision": True},
]
ANTHROPIC_FALLBACK = [
    {"id": "claude-opus-5-5", "label": "Claude Opus 5.5", "description": "Most capable.", "vision": True},
    {"id": "claude-sonnet-5-5", "label": "Claude Sonnet 5.5", "description": "Fast and strong.", "vision": True},
    {"id": "claude-haiku-5-5", "label": "Claude Haiku 5.5", "description": "Fastest.", "vision": True},
]
_model_cache: dict[str, tuple[float, list[dict]]] = {}


async def _fetch_api_models(provider: str, key: str) -> list[dict]:
    import time as _t
    hit = _model_cache.get(provider)
    if hit and _t.time() - hit[0] < 600 and hit[1]:
        return hit[1]
    out: list[dict] = []
    async with httpx.AsyncClient(timeout=8) as c:
        if provider == "openai":
            r = await c.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key}"})
            if r.status_code == 200:
                ids = sorted({m["id"] for m in r.json().get("data", [])}, reverse=True)
                skip = ("embedding", "whisper", "tts", "dall-e", "moderation", "audio", "realtime", "transcribe", "image", "search", "davinci", "babbage")
                out = [{"id": i, "label": i, "description": "", "vision": True} for i in ids
                       if (i.startswith("gpt") or i.startswith("o")) and not any(x in i for x in skip)]
        else:
            r = await c.get("https://api.anthropic.com/v1/models", headers={"x-api-key": key, "anthropic-version": "2023-06-01"})
            if r.status_code == 200:
                out = [{"id": m["id"], "label": m.get("display_name") or m["id"], "description": "", "vision": True}
                       for m in r.json().get("data", [])]
    _model_cache[provider] = (_t.time(), out)
    return out


async def model_catalog() -> dict:
    """Everything the model picker needs: which providers are ready and which models each one offers."""
    s = load_settings()
    status = await provider_status()
    cat = {}
    cm = codex_models()
    cat["codex"] = {"models": cm or [{"id": m, "label": m, "description": "", "vision": True,
                                         "efforts": EFFORTS, "default_effort": "medium"} for m in MODEL_SUGGESTIONS["codex"]],
                    "source": "your ChatGPT plan" if cm else "defaults"}
    cat["claude_code"] = {"models": [m | {"efforts": ["low", "medium", "high", "xhigh", "max"], "default_effort": "medium"}
                                     for m in CLAUDE_CODE_MODELS], "source": "your Claude plan"}
    for p in ("openai", "anthropic"):
        key = s["providers"][p].get("api_key")
        models, source = [], "needs an API key"
        if key:
            try:
                models = await _fetch_api_models(p, key)
                source = "your API key"
            except Exception:
                models, source = [], "could not reach the API"
        if not models:
            models = ANTHROPIC_FALLBACK if p == "anthropic" else [{"id": m, "label": m, "description": "", "vision": True}
                                                                     for m in MODEL_SUGGESTIONS["openai"]]
        effs = ["low", "medium", "high"] if p == "openai" else []
        cat[p] = {"models": [m | {"efforts": effs, "default_effort": "medium" if effs else ""} for m in models], "source": source}
    for p in cat:
        cat[p]["label"] = PROVIDERS[p]
        cat[p]["status"] = status[p]
    return cat


TIMEOUT = 900


class LLMError(Exception):
    pass


def _b64(path: str) -> tuple[str, str]:
    mime = mimetypes.guess_type(path)[0] or "image/png"
    return mime, base64.b64encode(Path(path).read_bytes()).decode()


def _flatten(system: str, messages: list[dict]) -> str:
    """For CLI agents that take a single prompt."""
    parts = [
        "Everything you need is in this prompt and in the attached images. Output only the requested text, with no preamble.",
        "",
        "=== SYSTEM INSTRUCTIONS ===",
        system.strip(),
    ]
    if len(messages) == 1 and messages[0]["role"] == "user":
        parts += ["", "=== INPUT ===", messages[0]["content"]]
    else:
        parts += ["", "=== CONVERSATION (oldest first) ==="]
        for m in messages:
            who = "STUDENT" if m["role"] == "user" else "ASSISTANT"
            parts += [f"--- {who} ---", m["content"]]
        parts += ["", "=== Write the next ASSISTANT message now. ==="]
    return "\n".join(parts)


def _flatten_body(messages: list[dict]) -> str:
    """The conversation alone (the instructions travel separately, as the worker thread's own instructions)."""
    if len(messages) == 1 and messages[0]["role"] == "user":
        return messages[0]["content"]
    parts = ["=== CONVERSATION (oldest first) ==="]
    for m in messages:
        parts += [f"--- {'STUDENT' if m['role'] == 'user' else 'ASSISTANT'} ---", m["content"]]
    parts += ["", "=== Write the next ASSISTANT message now. ==="]
    return "\n".join(parts)


def _all_images(messages: list[dict], limit: int = 8) -> list[str]:
    imgs = [p for m in messages for p in (m.get("images") or []) if Path(p).exists()]
    return imgs[-limit:]


async def _run(args: list[str], stdin: str, cwd: str | None = None) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *args, cwd=cwd,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(stdin.encode()), timeout=TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        raise LLMError("The model took too long and was stopped.")
    except asyncio.CancelledError:
        proc.kill()
        raise
    return proc.returncode, out.decode(errors="replace"), err.decode(errors="replace")


def friendly_error(provider: str, raw: str, model: str = "") -> str:
    """Turn CLI/API error dumps into one sentence a student can act on."""
    import re as _re
    low = raw.lower()
    m = _re.search(r'"message"\s*:\s*"([^"]+)"', raw)
    detail = m.group(1) if m else ""
    where = {"codex": "your ChatGPT plan", "claude_code": "your Claude plan", "openai": "your OpenAI key",
             "anthropic": "your Anthropic key"}.get(provider, provider)
    if "model_not_found" in low or ("model" in low and "not supported" in low) or "does not exist" in low:
        return f"The model “{model or '?'}” isn't available with {where}. Pick another one in Settings → Models."
    if "usage limit" in low or "rate limit" in low or "429" in low or "quota" in low:
        return f"You've hit the usage limit of {where}. Wait a bit, or switch to another provider in Settings → Models."
    if "not logged in" in low or "login" in low and "codex" in low or "unauthorized" in low or "401" in low:
        return f"Scaffold isn't signed in to {where}. Sign in again (for ChatGPT: run `codex login`)."
    if "network" in low or "connection" in low or "timed out" in low or "dns" in low:
        return "Couldn't reach the AI service. Check your internet connection and try again."
    return detail or raw[-300:]


# Scaffold's own agents only write text (they never run commands), so Codex's coding-agent instructions and tool
# descriptions are dead weight on every call (~6,500 tokens). Linked Codex chats are not affected: they run with
# the thread's full setup.
CODEX_TEXT_ONLY_FEATURES = ["apps", "browser_use", "browser_use_external", "computer_use", "code_mode_host", "goals",
                            "guardian_approval", "hooks", "image_generation", "multi_agent", "plugins", "skill_search",
                            "sleep_tool", "tool_suggest", "shell_tool", "unified_exec", "mentions_v2", "in_app_browser",
                            "realtime_conversation"]
CODEX_BASE = ("You are the language model behind one agent of Scaffold, a study app. The instructions and the input are "
              "in the user's message. Follow them exactly and reply with the requested text only. You cannot run "
              "commands or edit files; when asked for files, print them in your reply in the requested format.")

# token usage of the model calls made for the current answer (shown under it and logged)
usage_var: contextvars.ContextVar[list | None] = contextvars.ContextVar("scaffold_usage", default=None)


def _record_usage(role: str, model: str, usage: dict | None):
    if not usage:
        return
    entry = {"role": role, "model": model, "input": usage.get("input_tokens", 0),
             "cached": usage.get("cached_input_tokens", 0), "output": usage.get("output_tokens", 0)}
    acc = usage_var.get()
    if acc is not None:
        acc.append(entry)
    try:
        (WORKSPACE / "logs").mkdir(parents=True, exist_ok=True)
        import time as _t
        with open(WORKSPACE / "logs" / "usage.jsonl", "a") as f:
            f.write(json.dumps({**entry, "ts": round(_t.time())}) + "\n")
    except OSError:
        pass


def usage_summary(entries: list[dict]) -> dict:
    return {"input": sum(e["input"] for e in entries), "cached": sum(e["cached"] for e in entries),
            "output": sum(e["output"] for e in entries), "calls": len(entries)}


async def _codex(cfg: dict, system: str, messages: list[dict]) -> str:
    if not shutil.which("codex"):
        raise LLMError("Codex CLI not found. Install it and run `codex login`.")
    # a fixed, empty working folder: Codex puts its path near the top of the prompt, and a new random folder per call
    # would make every call look new to the provider's prompt cache
    run_dir = WORKSPACE / "cache" / "codex-run"
    run_dir.mkdir(parents=True, exist_ok=True)
    base = run_dir.parent / "codex-base.md"
    if not base.exists() or base.read_text() != CODEX_BASE:
        base.write_text(CODEX_BASE)
    if cfg.get("model") and load_settings().get("codex_pool", True):
        from .codexpool import POOL, PoolError
        try:
            text, usage = await POOL.run(model=cfg["model"], effort=cfg.get("effort") or None, base=CODEX_BASE,
                                         instructions=system, text=_flatten_body(messages), images=_all_images(messages),
                                         run_dir=run_dir, features_off=CODEX_TEXT_ONLY_FEATURES,
                                         role=cfg.get("_role", ""), timeout=TIMEOUT)
            if usage:
                _record_usage(cfg.get("_role", ""), cfg["model"], {"input_tokens": usage.get("inputTokens", 0),
                              "cached_input_tokens": usage.get("cachedInputTokens", 0),
                              "output_tokens": usage.get("outputTokens", 0)})
            return text
        except (PoolError, asyncio.TimeoutError, KeyError, OSError) as e:
            # the pool is an optimisation only: fall back to a plain one-off call
            (WORKSPACE / "logs").mkdir(parents=True, exist_ok=True)
            with open(WORKSPACE / "logs" / "codex-pool.log", "a") as f:
                f.write(f"{cfg.get('_role')}: fell back to codex exec: {e}\n")
    with tempfile.TemporaryDirectory(prefix="scaffold-codex-") as tmp:
        out_file = Path(tmp) / "last.txt"
        args = ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config", "--json",
                "-s", "read-only", "-C", str(run_dir), "-c", f'model_instructions_file="{base}"']
        for f in CODEX_TEXT_ONLY_FEATURES:
            args += ["-c", f"features.{f}=false"]
        if cfg.get("model"):
            args += ["-m", cfg["model"]]
        if cfg.get("effort"):
            args += ["-c", f'model_reasoning_effort="{cfg["effort"]}"']
        imgs = _all_images(messages)
        if imgs:
            args += ["-i", *imgs]
        args += ["-o", str(out_file)]  # a flag after -i ends the image list; prompt comes on stdin
        code, out, err = await _run(args, _flatten(system, messages), cwd=str(run_dir))
        for line in out.splitlines():
            if '"turn.completed"' in line:
                try:
                    _record_usage(cfg.get("_role", ""), cfg.get("model", ""), json.loads(line).get("usage"))
                except Exception:
                    pass
        text = out_file.read_text() if out_file.exists() else ""
        if code == 0 and not text.strip():
            return ""
        if code != 0 or not text.strip():
            (WORKSPACE / "logs").mkdir(parents=True, exist_ok=True)
            (WORKSPACE / "logs" / "codex-last-failure.log").write_text(f"exit {code}\n--- stdout\n{out[-20000:]}\n--- stderr\n{err[-20000:]}")
            raise LLMError(friendly_error("codex", err + "\n" + out, cfg.get("model", "")))
        return text


async def _claude_code(cfg: dict, system: str, messages: list[dict]) -> str:
    if not shutil.which("claude"):
        raise LLMError("Claude Code CLI not found. Install it and log in.")
    # The system prompt goes in --system-prompt; the conversation goes in one user turn.
    convo = _flatten("(see system prompt)", messages)
    content = [{"type": "text", "text": convo}]
    for p in _all_images(messages):
        mime, data = _b64(p)
        content.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}})
    line = json.dumps({"type": "user", "message": {"role": "user", "content": content}})
    with tempfile.TemporaryDirectory(prefix="scaffold-claude-") as tmp:
        args = ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json",
                "--verbose", "--system-prompt", system, "--tools", "", "--no-session-persistence",
                "--setting-sources", ""]
        if cfg.get("model"):
            args += ["--model", cfg["model"]]
        if cfg.get("effort"):
            args += ["--effort", cfg["effort"]]
        code, out, err = await _run(args, line + "\n", cwd=tmp)
    result = None
    for raw in out.splitlines():
        try:
            ev = json.loads(raw)
        except Exception:
            continue
        if ev.get("type") == "result":
            if ev.get("is_error"):
                raise LLMError("Claude Code: " + str(ev.get("result") or ev))
            result = ev.get("result")
            u = ev.get("usage") or {}
            cached = u.get("cache_read_input_tokens", 0)
            _record_usage(cfg.get("_role", ""), cfg.get("model", ""),
                          {"input_tokens": u.get("input_tokens", 0) + cached + u.get("cache_creation_input_tokens", 0),
                           "cached_input_tokens": cached, "output_tokens": u.get("output_tokens", 0)})
    if result is None and code != 0:
        raise LLMError("Claude Code failed: " + (err or out)[-400:])
    return result or ""


async def _openai(cfg: dict, system: str, messages: list[dict]) -> str:
    key = load_settings()["providers"]["openai"].get("api_key")
    if not key:
        raise LLMError("No OpenAI API key. Add it in Settings → Models.")
    msgs = [{"role": "system", "content": system}]
    for m in messages:
        if m.get("images") and m["role"] == "user":
            parts = [{"type": "text", "text": m["content"]}]
            for p in m["images"]:
                if Path(p).exists():
                    mime, data = _b64(p)
                    parts.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}})
            msgs.append({"role": "user", "content": parts})
        else:
            msgs.append({"role": m["role"], "content": m["content"]})
    body = {"model": cfg.get("model") or "gpt-6.1-sol", "messages": msgs}
    if cfg.get("effort"):
        body["reasoning_effort"] = cfg["effort"]
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.post("https://api.openai.com/v1/chat/completions",
                         headers={"Authorization": f"Bearer {key}"}, json=body)
        if r.status_code == 400 and "reasoning_effort" in r.text:
            body.pop("reasoning_effort")
            r = await c.post("https://api.openai.com/v1/chat/completions",
                             headers={"Authorization": f"Bearer {key}"}, json=body)
    if r.status_code != 200:
        raise LLMError(f"OpenAI error {r.status_code}: {r.text[:300]}")
    data = r.json()
    u = data.get("usage") or {}
    _record_usage(cfg.get("_role", ""), body["model"], {"input_tokens": u.get("prompt_tokens", 0),
                  "cached_input_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0),
                  "output_tokens": u.get("completion_tokens", 0)})
    return data["choices"][0]["message"]["content"] or ""


async def _anthropic(cfg: dict, system: str, messages: list[dict]) -> str:
    key = load_settings()["providers"]["anthropic"].get("api_key")
    if not key:
        raise LLMError("No Anthropic API key. Add it in Settings → Models.")
    msgs = []
    for m in messages:
        parts = []
        if m["role"] == "user":
            for p in m.get("images") or []:
                if Path(p).exists():
                    mime, data = _b64(p)
                    parts.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}})
        parts.append({"type": "text", "text": m["content"] or "(empty)"})
        msgs.append({"role": m["role"], "content": parts})
    # cache the system prompt (it repeats on every call of the same agent)
    body = {"model": cfg.get("model") or "claude-sonnet-5-5", "max_tokens": 16000,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}], "messages": msgs}
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.post("https://api.anthropic.com/v1/messages", json=body, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01"})
    if r.status_code != 200:
        raise LLMError(f"Anthropic error {r.status_code}: {r.text[:300]}")
    data = r.json()
    u = data.get("usage") or {}
    cached = u.get("cache_read_input_tokens", 0)
    _record_usage(cfg.get("_role", ""), body["model"], {"input_tokens": u.get("input_tokens", 0) + cached + u.get("cache_creation_input_tokens", 0),
                  "cached_input_tokens": cached, "output_tokens": u.get("output_tokens", 0)})
    return "".join(b.get("text", "") for b in data["content"] if b["type"] == "text")


_IMPL = {"codex": _codex, "claude_code": _claude_code, "openai": _openai, "anthropic": _anthropic}


class EmptyReply(LLMError):
    pass


async def complete(role: str, system: str, messages: list[dict]) -> str:
    """One model call. Empty or failed replies are retried automatically (up to 2 more tries)."""
    cfg = dict(load_settings()["roles"].get(role) or load_settings()["roles"]["tutor"])
    cfg["_role"] = role
    impl = _IMPL.get(cfg.get("provider"))
    if not impl:
        raise LLMError(f"Unknown provider: {cfg.get('provider')}")
    last: Exception | None = None
    for attempt in range(3):
        msgs = messages
        if attempt and messages:
            # nudge: some CLI runs end without a final message
            tail = dict(messages[-1])
            tail["content"] = tail.get("content", "") + "\n\n(Reply now, in plain text, without using any tools.)"
            msgs = messages[:-1] + [tail]
        try:
            out = (await impl(cfg, system, msgs)).strip()
            if out:
                return out
            last = EmptyReply("The model returned an empty reply.")
        except LLMError as e:
            last = e
            msg = str(e).lower()
            # do not retry problems that will not fix themselves
            if any(k in msg for k in ("isn't available", "usage limit", "isn't signed in", "not found", "no openai api key", "no anthropic api key", "unknown provider",
                                      "invalid", "does not exist", "unsupported", "401", "403", "404")):
                raise
        await asyncio.sleep(1.5 * (attempt + 1))
    raise last or LLMError("The model did not answer.")


async def provider_status() -> dict:
    s = load_settings()
    out = {}
    codex = shutil.which("codex")
    codex_ok = False
    if codex:
        try:
            code, o, e = await _run(["codex", "login", "status"], "")
            codex_ok = code == 0 and "logged in" in (o + e).lower()
        except Exception:
            pass
    out["codex"] = {"installed": bool(codex), "ready": codex_ok,
                    "detail": "Logged in with ChatGPT" if codex_ok else ("Run `codex login`" if codex else "Not installed")}
    claude = shutil.which("claude")
    out["claude_code"] = {"installed": bool(claude), "ready": bool(claude),
                          "detail": "CLI found (uses your Claude login)" if claude else "Not installed"}
    for p in ("openai", "anthropic"):
        has = bool(s["providers"][p].get("api_key"))
        out[p] = {"installed": True, "ready": has, "detail": "API key saved" if has else "No API key"}
    return out
