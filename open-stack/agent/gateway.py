"""Call Claude through a Bedrock-compatible gateway, the same way Claude Code does.

Reads the gateway from the environment Claude Code already uses:

    ANTHROPIC_BEDROCK_BASE_URL   gateway base URL
    ANTHROPIC_CUSTOM_HEADERS     extra headers, one "Name: value" per line
    ANTHROPIC_DEFAULT_OPUS_MODEL Bedrock model ID (default us.anthropic.claude-opus-5-5)
    GATEWAY_API_KEY              the key, if set; otherwise the output of Claude Code's
                                 apiKeyHelper command (~/.claude/settings.json)

The key and header values are secrets: they are sent to the gateway and never logged,
traced or stored.
The agent speaks OpenAI-style messages; this module converts to and from the Anthropic
Messages format that Bedrock's InvokeModel expects.
"""

from __future__ import annotations

import asyncio
import json
import os
import ssl
import subprocess
from pathlib import Path

import httpx
import truststore

from agent.v0 import CompletionFn

DEFAULT_GATEWAY_MODEL = os.environ.get("ANTHROPIC_DEFAULT_OPUS_MODEL", "us.anthropic.claude-opus-5-5")
RETRY_STATUSES = {429, 500, 502, 503, 504, 529}

# USD per million tokens (input, output), for the cost column in traces only.
PRICES = {"opus": (5.0, 25.0), "sonnet": (3.0, 15.0), "haiku": (1.0, 5.0)}


def parse_headers(raw: str) -> dict[str, str]:
    headers = {}
    for line in raw.splitlines():
        name, sep, value = line.partition(":")
        if sep and name.strip():
            headers[name.strip()] = value.strip()
    return headers


def to_anthropic(messages: list[dict], tools: list[dict]) -> dict:
    """OpenAI-style chat messages and tool specs -> an Anthropic Messages request body."""
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    out: list[dict] = []
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": [{"type": "text", "text": m["content"]}]})
        elif m["role"] == "assistant":
            blocks = [{"type": "text", "text": m["content"]}] if m.get("content") else []
            blocks += [{"type": "tool_use", "id": tc["id"], "name": tc["function"]["name"],
                        "input": json.loads(tc["function"]["arguments"] or "{}")}
                       for tc in m.get("tool_calls", [])]
            out.append({"role": "assistant", "content": blocks})
        elif m["role"] == "tool":
            block = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
            if out and out[-1]["role"] == "user" and out[-1]["content"][0]["type"] == "tool_result":
                out[-1]["content"].append(block)  # parallel tool results share one user turn
            else:
                out.append({"role": "user", "content": [block]})
    body = {"anthropic_version": "bedrock-2023-05-31", "messages": out}
    if system:
        body["system"] = system
    if tools:
        body["tools"] = [{"name": t["function"]["name"], "description": t["function"]["description"],
                          "input_schema": t["function"]["parameters"]} for t in tools]
    return body


def from_anthropic(resp: dict, model: str) -> tuple[dict, dict]:
    """An Anthropic Messages response -> (OpenAI-style assistant message, usage)."""
    text = "".join(b["text"] for b in resp["content"] if b["type"] == "text")
    assistant: dict = {"role": "assistant", "content": text}
    calls = [{"id": b["id"], "type": "function",
              "function": {"name": b["name"], "arguments": json.dumps(b["input"])}}
             for b in resp["content"] if b["type"] == "tool_use"]
    if calls:
        assistant["tool_calls"] = calls
    u = resp.get("usage", {})
    tokens_in = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
    tokens_out = u.get("output_tokens", 0)
    price_in, price_out = next((p for k, p in PRICES.items() if k in model), (0.0, 0.0))
    cost = (tokens_in * price_in + tokens_out * price_out) / 1e6
    return assistant, {"input_tokens": tokens_in, "output_tokens": tokens_out, "cost_usd": cost}


CLAUDE_SETTINGS = Path("~/.claude/settings.json").expanduser()


def gateway_api_key() -> str:
    """GATEWAY_API_KEY, or the output of Claude Code's apiKeyHelper. Never logged."""
    if os.environ.get("GATEWAY_API_KEY"):
        return os.environ["GATEWAY_API_KEY"]
    helper = json.loads(CLAUDE_SETTINGS.read_text()).get("apiKeyHelper") if CLAUDE_SETTINGS.exists() else None
    if not helper:
        raise SystemExit("No gateway key: set GATEWAY_API_KEY or configure apiKeyHelper in Claude Code.")
    out = subprocess.run(helper, shell=True, capture_output=True, text=True, timeout=120)
    key = out.stdout.strip()
    if out.returncode != 0 or not key:
        raise SystemExit(f"apiKeyHelper failed (exit {out.returncode}); no key was returned.")
    return key


def ssl_context() -> ssl.SSLContext:
    """Trust what the OS trusts (e.g. a corporate CA in the macOS keychain), not just certifi.

    SSL_CERT_FILE and NODE_EXTRA_CA_CERTS (Claude Code's CA file), if set, are added on top.
    """
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    for var in ("SSL_CERT_FILE", "NODE_EXTRA_CA_CERTS"):
        if os.environ.get(var) and Path(os.environ[var]).is_file():
            ctx.load_verify_locations(os.environ[var])
    return ctx


def gateway_completion(model: str = DEFAULT_GATEWAY_MODEL, max_tokens: int = 4096,
                       attempts: int = 4) -> CompletionFn:
    base = os.environ.get("ANTHROPIC_BEDROCK_BASE_URL")
    if not base:
        raise SystemExit("ANTHROPIC_BEDROCK_BASE_URL is not set; the gateway backend needs it.")
    url = f"{base.rstrip('/')}/model/{model}/invoke"
    headers = {**parse_headers(os.environ.get("ANTHROPIC_CUSTOM_HEADERS", "")),
               "authorization": f"Bearer {gateway_api_key()}",
               "content-type": "application/json"}

    verify = ssl_context()

    async def complete(messages: list[dict], tools: list[dict]) -> tuple[dict, dict]:
        body = {**to_anthropic(messages, tools), "max_tokens": max_tokens}
        async with httpx.AsyncClient(timeout=300, verify=verify) as client:
            for attempt in range(attempts):
                r = await client.post(url, headers=headers, json=body)
                if r.status_code not in RETRY_STATUSES or attempt == attempts - 1:
                    break
                await asyncio.sleep(2 ** attempt * 2)
        if r.status_code != 200:
            raise RuntimeError(f"Gateway returned HTTP {r.status_code}: {r.text[:300]}")
        return from_anthropic(r.json(), model)

    return complete
