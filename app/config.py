"""Application settings, read from environment variables (and a local .env file in development).

On Vercel every value comes from Project Settings -> Environment Variables. AWS credentials use a
DDB_ prefix because Vercel reserves the AWS_* variable names for its own runtime.
"""

from __future__ import annotations

import json
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_name: str = "portfolio-rag-api"
    app_version: str = "0.1.0"
    app_env: str = "development"  # set APP_ENV=production on Vercel

    # --- CORS ---
    # Comma-separated exact origins, e.g. "https://abhay-bhardwaj.netlify.app,http://localhost:8080"
    allowed_origins: str = "https://abhay-bhardwaj.netlify.app"
    # Optional regex for preview deployments, e.g. r"https://.*\.lovable\.app"
    allowed_origin_regex: str | None = None

    # --- Qdrant Cloud (vector store + Cloud Inference embeddings) ---
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_collection: str = "portfolio_kb"
    # Copy the exact model id from the cluster's Inference tab.
    embedding_model: str = "sentence-transformers/all-minilm-l6-v2"
    embedding_dim: int = 384

    # --- DynamoDB ---
    ddb_access_key_id: str | None = None
    ddb_secret_access_key: str | None = None
    ddb_region: str = "us-east-1"
    ddb_table_prefix: str = "portfolio-rag-"

    # --- LLM (G4F) ---
    g4f_model: str = "gpt-4"
    llm_timeout_seconds: float = 45.0

    # --- GitHub (used from step 1b) ---
    # JSON object mapping each repo owner (user or org) to its own fine-grained token:
    #   {"my-ai-org": "github_pat_...", "my-other-org": "github_pat_..."}
    # One token per owner, because a fine-grained PAT can target only one resource owner.
    github_tokens: str = ""

    # --- Health checks ---
    health_check_timeout_seconds: float = 5.0

    # ---------- derived values ----------
    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    @property
    def origins(self) -> list[str]:
        seen: list[str] = []
        for raw in self.allowed_origins.split(","):
            origin = raw.strip().rstrip("/")
            if origin and origin not in seen:
                seen.append(origin)
        return seen

    @property
    def qdrant_configured(self) -> bool:
        return bool(self.qdrant_url and self.qdrant_api_key)

    @property
    def dynamodb_configured(self) -> bool:
        return bool(self.ddb_access_key_id and self.ddb_secret_access_key)

    def table_name(self, suffix: str) -> str:
        """portfolio-rag-<suffix>; the IAM policy grants access to portfolio-rag-* only."""
        return f"{self.ddb_table_prefix}{suffix}"

    @property
    def github_token_map(self) -> dict[str, str]:
        """Owner (lower-cased) -> token. Raises ValueError without echoing any token value."""
        raw = self.github_tokens.strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError("GITHUB_TOKENS must be a JSON object like {\"owner\": \"token\"}.") from None
        if not isinstance(data, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip()
            for k, v in data.items()
        ):
            raise ValueError("GITHUB_TOKENS must map non-empty owner names to non-empty token strings.")
        return {k.strip().lower(): v.strip() for k, v in data.items()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
