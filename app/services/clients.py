"""Cached clients for Qdrant and DynamoDB.

Clients are created lazily and reused across requests while a Vercel function instance stays warm.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config import Settings


class NotConfiguredError(RuntimeError):
    """A required service has no credentials configured."""


@lru_cache(maxsize=4)
def _qdrant_client(url: str, api_key: str, timeout: int) -> Any:
    from qdrant_client import QdrantClient  # imported lazily to keep cold starts light

    # cloud_inference=True makes Qdrant Cloud compute embeddings for models.Document inputs.
    return QdrantClient(url=url, api_key=api_key, timeout=timeout, cloud_inference=True)


def get_qdrant_client(settings: Settings) -> Any:
    if not settings.qdrant_configured:
        raise NotConfiguredError("QDRANT_URL / QDRANT_API_KEY are not set.")
    return _qdrant_client(
        settings.qdrant_url, settings.qdrant_api_key, max(1, int(settings.health_check_timeout_seconds))
    )


@lru_cache(maxsize=4)
def _dynamodb_client(access_key: str, secret_key: str, region: str, timeout: float) -> Any:
    import boto3
    from botocore.config import Config

    return boto3.client(
        "dynamodb",
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(connect_timeout=timeout, read_timeout=timeout, retries={"max_attempts": 2}),
    )


def get_dynamodb_client(settings: Settings) -> Any:
    if not settings.dynamodb_configured:
        raise NotConfiguredError("DDB_ACCESS_KEY_ID / DDB_SECRET_ACCESS_KEY are not set.")
    return _dynamodb_client(
        settings.ddb_access_key_id,
        settings.ddb_secret_access_key,
        settings.ddb_region,
        settings.health_check_timeout_seconds,
    )
