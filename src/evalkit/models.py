"""Claude model adapter. Requires the `anthropic` package."""

from __future__ import annotations

import os

from .graders import ModelFn

DEFAULT_MODEL = os.environ.get("EVALKIT_MODEL", "claude-opus-5-5")


def claude(model: str = DEFAULT_MODEL, effort: str = "medium", max_tokens: int = 16000) -> ModelFn:
    """Return an async (system, prompt) -> text function backed by the Claude API."""
    import anthropic

    client = anthropic.AsyncAnthropic()
    extra = {}
    if model.startswith(("claude-opus-5", "claude-fable-5-1")):
        # Server-side refusal fallback: the API retries a declined request on a fallback model.
        extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}

    async def call(system: str | None, prompt: str) -> str:
        kwargs = dict(extra)
        if system:
            kwargs["system"] = system
        response = await client.beta.messages.create(
            model=model,
            max_tokens=max_tokens,
            output_config={"effort": effort},
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("model declined the request")
        return "".join(b.text for b in response.content if b.type == "text")

    return call
