"""Live checks for each backend dependency. Every status comes from a real call, never assumed."""

from __future__ import annotations

import logging
import time

from app.config import Settings
from app.schemas import HealthComponent
from app.services import clients, llm

logger = logging.getLogger(__name__)

# Table probed by the DynamoDB check (created by the table script in step 1b).
PROBE_TABLE_SUFFIX = "documents"

_CREDENTIAL_ERRORS = {
    "AccessDeniedException",
    "UnrecognizedClientException",
    "InvalidSignatureException",
    "IncompleteSignature",
    "ExpiredTokenException",
}


def _ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


class HealthChecker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def check_qdrant(self) -> HealthComponent:
        s = self.settings
        if not s.qdrant_configured:
            return HealthComponent(status="not_configured", detail="QDRANT_URL / QDRANT_API_KEY are not set.")
        start = time.perf_counter()
        try:
            names = {c.name for c in clients.get_qdrant_client(s).get_collections().collections}
        except Exception as exc:
            logger.warning("Qdrant health check failed: %r", exc)
            return HealthComponent(
                status="down",
                detail=f"Cluster unreachable or API key rejected ({type(exc).__name__}).",
                latency_ms=_ms(start),
            )
        latency = _ms(start)
        if s.qdrant_collection in names:
            return HealthComponent(
                status="ok", detail=f"Collection '{s.qdrant_collection}' is ready.", latency_ms=latency
            )
        return HealthComponent(
            status="degraded",
            detail=f"Cluster reachable; collection '{s.qdrant_collection}' not created yet "
            "(it is created by the first ingestion).",
            latency_ms=latency,
        )

    def check_dynamodb(self) -> HealthComponent:
        s = self.settings
        if not s.dynamodb_configured:
            return HealthComponent(
                status="not_configured", detail="DDB_ACCESS_KEY_ID / DDB_SECRET_ACCESS_KEY are not set."
            )
        from botocore.exceptions import BotoCoreError, ClientError

        table = s.table_name(PROBE_TABLE_SUFFIX)
        start = time.perf_counter()
        try:
            # DescribeTable is allowed by the IAM policy on portfolio-rag-* tables; IAM is checked
            # before existence, so "not found" still proves the keys, policy and region are right.
            desc = clients.get_dynamodb_client(s).describe_table(TableName=table)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "ClientError")
            latency = _ms(start)
            if code == "ResourceNotFoundException":
                return HealthComponent(
                    status="degraded",
                    detail=f"Credentials work in {s.ddb_region}; table '{table}' not created yet.",
                    latency_ms=latency,
                )
            logger.warning("DynamoDB health check failed: %s", code)
            if code in _CREDENTIAL_ERRORS:
                detail = f"Credentials or IAM policy rejected ({code})."
            else:
                detail = f"DynamoDB error ({code})."
            return HealthComponent(status="down", detail=detail, latency_ms=latency)
        except BotoCoreError as exc:
            logger.warning("DynamoDB health check failed: %r", exc)
            return HealthComponent(
                status="down", detail=f"DynamoDB unreachable ({type(exc).__name__}).", latency_ms=_ms(start)
            )

        latency = _ms(start)
        table_status = desc.get("Table", {}).get("TableStatus", "UNKNOWN")
        if table_status == "ACTIVE":
            return HealthComponent(status="ok", detail=f"Table '{table}' is ACTIVE.", latency_ms=latency)
        return HealthComponent(
            status="degraded", detail=f"Table '{table}' is {table_status}.", latency_ms=latency
        )

    async def check_llm(self) -> HealthComponent:
        """Live G4F round trip. Only run on ?deep=true because it is slow and uses the provider."""
        s = self.settings
        start = time.perf_counter()
        try:
            await llm.complete(
                [{"role": "user", "content": "Reply with exactly one word: pong"}],
                model=s.g4f_model,
                timeout=min(s.llm_timeout_seconds, 25.0),
            )
        except llm.LLMTimeoutError as exc:
            return HealthComponent(status="down", detail=f"G4F timed out ({exc}).", latency_ms=_ms(start))
        except llm.LLMError as exc:
            logger.warning("G4F health check failed: %s", exc)
            return HealthComponent(status="down", detail=f"G4F call failed ({exc}).", latency_ms=_ms(start))
        return HealthComponent(
            status="ok", detail=f"G4F answered (model '{s.g4f_model}').", latency_ms=_ms(start)
        )
