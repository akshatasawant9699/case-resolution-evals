"""Pick how the agent reaches a model: LiteLLM (provider key) or Claude Code's gateway."""

from __future__ import annotations

from agent import v0


def make_completion(backend: str = "gateway", model: str | None = None) -> tuple[v0.CompletionFn, str]:
    """Return (completion_fn, model name)."""
    if backend == "gateway":
        from agent.gateway import DEFAULT_GATEWAY_MODEL, gateway_completion
        model = model or DEFAULT_GATEWAY_MODEL
        return gateway_completion(model), model
    if backend == "litellm":
        model = model or v0.DEFAULT_MODEL
        return v0.litellm_completion(model), model
    raise ValueError(f"Unknown backend {backend!r}; use 'gateway' or 'litellm'.")
