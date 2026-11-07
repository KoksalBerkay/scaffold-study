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
import json
import mimetypes
import shutil
import tempfile
from pathlib import Path

import httpx

from .config import load_settings

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
    """Read the Codex CLI's own model cache so the UI shows real models and reasoning levels."""
    for f in sorted(Path.home().glob(".codex/*models*.json")):
        try:
            d = json.loads(f.read_text())
            ms = d.get("models", d) if isinstance(d, dict) else d
            out = []
            for m in ms:
                slug = m.get("slug") or m.get("id")
                if slug and "review" not in slug:
                    out.append({"id": slug, "efforts": [e.get("effort") for e in m.get("supported_reasoning_levels", [])]})
            if out:
                return out
        except Exception:
            continue
    return []

TIMEOUT = 900


class LLMError(Exception):
    pass


def _b64(path: str) -> tuple[str, str]:
    mime = mimetypes.guess_type(path)[0] or "image/png"
    return mime, base64.b64encode(Path(path).read_bytes()).decode()


def _flatten(system: str, messages: list[dict]) -> str:
    """For CLI agents that take a single prompt."""
    parts = [
        "You are being used as a plain text-generation backend inside a study app. "
        "Do not run shell commands, do not read or write files, do not browse. "
        "Everything you need is in this prompt and in the attached images. "
        "Output only the requested text, with no preamble.",
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


async def _codex(cfg: dict, system: str, messages: list[dict]) -> str:
    if not shutil.which("codex"):
        raise LLMError("Codex CLI not found. Install it and run `codex login`.")
    with tempfile.TemporaryDirectory(prefix="scaffold-codex-") as tmp:
        out_file = Path(tmp) / "last.txt"
        args = ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config",
                "-s", "read-only", "-C", tmp]
        if cfg.get("model"):
            args += ["-m", cfg["model"]]
        if cfg.get("effort"):
            args += ["-c", f'model_reasoning_effort="{cfg["effort"]}"']
        imgs = _all_images(messages)
        if imgs:
            args += ["-i", *imgs]
        args += ["-o", str(out_file)]  # a flag after -i ends the image list; prompt comes on stdin
        code, out, err = await _run(args, _flatten(system, messages), cwd=tmp)
        text = out_file.read_text() if out_file.exists() else ""
        if code != 0 or not text.strip():
            tail = (err or out).strip().splitlines()[-6:]
            raise LLMError("Codex failed: " + " | ".join(tail))
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
    if not result:
        raise LLMError("Claude Code failed: " + (err or out)[-400:])
    return result


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
    return r.json()["choices"][0]["message"]["content"] or ""


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
    body = {"model": cfg.get("model") or "claude-sonnet-5-5", "max_tokens": 16000,
            "system": system, "messages": msgs}
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.post("https://api.anthropic.com/v1/messages", json=body, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01"})
    if r.status_code != 200:
        raise LLMError(f"Anthropic error {r.status_code}: {r.text[:300]}")
    return "".join(b.get("text", "") for b in r.json()["content"] if b["type"] == "text")


_IMPL = {"codex": _codex, "claude_code": _claude_code, "openai": _openai, "anthropic": _anthropic}


async def complete(role: str, system: str, messages: list[dict]) -> str:
    cfg = load_settings()["roles"].get(role) or load_settings()["roles"]["tutor"]
    impl = _IMPL.get(cfg.get("provider"))
    if not impl:
        raise LLMError(f"Unknown provider: {cfg.get('provider')}")
    return (await impl(cfg, system, messages)).strip()


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
