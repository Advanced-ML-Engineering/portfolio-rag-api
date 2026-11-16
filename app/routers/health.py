from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings
from app.schemas import HealthComponent, HealthResponse
from app.services.health import HealthChecker

router = APIRouter(prefix="/api/v1", tags=["health"])


def get_health_checker(settings: Settings = Depends(get_settings)) -> HealthChecker:
    return HealthChecker(settings)


@router.get("/health", response_model=HealthResponse, response_model_exclude_none=True)
async def health(
    deep: bool = Query(False, description="Also make a live G4F call (slow)."),
    settings: Settings = Depends(get_settings),
    checker: HealthChecker = Depends(get_health_checker),
) -> HealthResponse:
    names = ["qdrant", "dynamodb"]
    jobs = [asyncio.to_thread(checker.check_qdrant), asyncio.to_thread(checker.check_dynamodb)]
    if deep:
        # The LLM is only reported when it was actually called; otherwise the frontend shows it as
        # "not reported" instead of a guessed status.
        names.append("llm")
        jobs.append(checker.check_llm())

    results: list[HealthComponent] = list(await asyncio.gather(*jobs))
    components = dict(zip(names, results, strict=True))
    overall = "ok" if all(c.status == "ok" for c in results) else "degraded"
    return HealthResponse(
        status=overall, version=settings.app_version, environment=settings.app_env, components=components
    )
