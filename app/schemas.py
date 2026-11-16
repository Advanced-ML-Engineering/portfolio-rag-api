"""Response models. Shapes match the frontend's zod schemas in src/lib/rag-api.ts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# The frontend maps "ok" -> online, "degraded" -> degraded, anything else -> offline.
ComponentState = Literal["ok", "degraded", "down", "not_configured"]


class HealthComponent(BaseModel):
    status: ComponentState
    detail: str | None = None
    latency_ms: int | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    environment: str
    components: dict[str, HealthComponent]
