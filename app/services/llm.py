"""G4F wrapper.

Uses the same call as the existing Flask app:
    g4f.ChatCompletion.create(model="gpt-4", messages=[...])
The call is blocking, so it runs in a worker thread with a timeout. There is no fallback provider:
on failure callers get an LLMError and must report the service as unavailable.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable


class LLMError(RuntimeError):
    """G4F failed or returned nothing usable."""


class LLMTimeoutError(LLMError):
    """G4F did not answer in time."""


async def complete(messages: list[dict[str, str]], *, model: str, timeout: float) -> str:
    try:
        import g4f  # lazy: heavy import, only needed when the LLM is actually called
    except ImportError as exc:  # pragma: no cover - depends on the installed packages
        raise LLMError("g4f is not installed") from exc

    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(g4f.ChatCompletion.create, model=model, messages=messages),
            timeout=timeout,
        )
    except TimeoutError as exc:
        raise LLMTimeoutError(f"no answer within {timeout:g}s") from exc
    except Exception as exc:  # G4F raises many provider-specific exception types
        raise LLMError(type(exc).__name__) from exc

    text = response if isinstance(response, str) else _join_chunks(response)
    if not text.strip():
        raise LLMError("empty response")
    return text


def _join_chunks(response: object) -> str:
    if isinstance(response, Iterable):
        return "".join(str(chunk) for chunk in response)
    return str(response)
