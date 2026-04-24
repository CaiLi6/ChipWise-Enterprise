"""Settings loader: YAML config + environment variable overrides + validation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

# ── Sub-models ──────────────────────────────────────────────────────

class LLMEndpointSettings(BaseModel):
    provider: str = "openai_compatible"
    base_url: str = "http://localhost:1234/v1"
    model: str = ""
    api_key: str = "lm-studio"
    max_tokens: int = 4096
    temperature: float = 0.1
    timeout: int = 90
    max_concurrent: int = 2


class LLMSettings(BaseModel):
    primary: LLMEndpointSettings = Field(default_factory=LLMEndpointSettings)
    router: LLMEndpointSettings = Field(default_factory=LLMEndpointSettings)
    extractor: LLMEndpointSettings | None = None


class EmbeddingSettings(BaseModel):
    provider: str = "fastapi_remote"
    base_url: str = "http://localhost:8001"
    model: str = "BAAI/bge-m3"
    dim: int = 1024
    batch_size: int = 32
    timeout: int = 30


class RerankSettings(BaseModel):
    provider: str = "fastapi_remote"
    base_url: str = "http://localhost:8002"
    model: str = "maidalun1020/bce-reranker-base_v1"
    top_k: int = 10
    timeout: int = 10
    enabled: bool = True


class MilvusSettings(BaseModel):
    host: str = "localhost"
    port: int = 19530
    collection_name: str = "datasheet_chunks"
    consistency_level: str = "Session"


class VectorStoreSettings(BaseModel):
    backend: str = "milvus"
    milvus: MilvusSettings = Field(default_factory=MilvusSettings)


class DatabaseSettings(BaseModel):
    host: str = "localhost"
    port: int = 5432
    database: str = "chipwise"
    user: str = "chipwise"
    password: str = ""
    pool_size: int = 10
    max_overflow: int = 5


class RedisSettings(BaseModel):
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    celery_db: int = 1
    password: str = ""


class RetrievalSettings(BaseModel):
    mode: str = "hybrid"
    sparse_method: str = "bgem3"
    top_k_search: int = 30
    top_k_rerank: int = 10
    rrf_k: int = 60


class CacheSettings(BaseModel):
    enabled: bool = True
    similarity_threshold: float = 0.95
    ttl_conversational: int = 3600
    ttl_comparison: int = 14400


class RateLimitSettings(BaseModel):
    per_user_per_minute: int = 30
    per_user_per_hour: int = 500
    global_primary_llm_concurrent: int = 2
    global_router_llm_concurrent: int = 10


class AgentSettings(BaseModel):
    max_iterations: int = 5
    max_total_tokens: int = 8192
    parallel_tool_calls: bool = True
    temperature: float = 0.1
    tool_timeout: float = 30.0
    max_observation_chars: int = 4000


class KuzuSettings(BaseModel):
    db_path: str = "data/kuzu"


class GraphStoreSettings(BaseModel):
    backend: str = "kuzu"
    kuzu: KuzuSettings = Field(default_factory=KuzuSettings)


class SSOSettings(BaseModel):
    provider: str = "keycloak"
    issuer: str = ""
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = ""
    scopes: list[str] = Field(default_factory=lambda: ["openid", "profile", "email"])
    group_role_mapping: dict[str, str] = Field(default_factory=dict)


class JWTSettings(BaseModel):
    algorithm: str = "RS256"
    private_key_path: str = ""
    public_key_path: str = ""
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7


class LocalFallbackSettings(BaseModel):
    enabled: bool = True
    jwt_secret: str = ""


class AuthSettings(BaseModel):
    mode: str = "sso"
    sso: SSOSettings = Field(default_factory=SSOSettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)
    local_fallback: LocalFallbackSettings = Field(default_factory=LocalFallbackSettings)


class ObservabilitySettings(BaseModel):
    trace_log_file: str = "./logs/traces.jsonl"
    app_log_file: str = "./logs/app.log"
    log_level: str = "INFO"
    celery_log_file: str = "./logs/celery.log"


class FrontendSettings(BaseModel):
    type: str = "gradio"
    port: int = 7860
    share: bool = False


class ChunkingSettings(BaseModel):
    strategy: str = "datasheet"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    separator: list[str] = Field(default_factory=lambda: ["\n\n", "\n", ". ", " "])
    params: dict[str, dict[str, Any]] = Field(default_factory=dict)


class CrawlerSettings(BaseModel):
    schedule: str = "0 2 * * *"
    max_per_run: int = 50


class WatchdogSettings(BaseModel):
    paths: list[str] = Field(default_factory=list)
    debounce_seconds: int = 5
    file_types: list[str] = Field(default_factory=lambda: [".pdf"])


class PdfExtractorSettings(BaseModel):
    tier1: str = "pdfplumber"
    tier2: str = "camelot"
    tier3: str = "paddleocr"


class IngestionSettings(BaseModel):
    pdf_extractor: PdfExtractorSettings = Field(default_factory=PdfExtractorSettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    crawler: CrawlerSettings = Field(default_factory=CrawlerSettings)
    watchdog: WatchdogSettings = Field(default_factory=WatchdogSettings)


# ── Root Settings ───────────────────────────────────────────────────

class Settings(BaseModel):
    """Root configuration — loaded from config/settings.yaml with env overrides."""

    llm: LLMSettings = Field(default_factory=LLMSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    rerank: RerankSettings = Field(default_factory=RerankSettings)
    vector_store: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    graph_store: GraphStoreSettings = Field(default_factory=GraphStoreSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    frontend: FrontendSettings = Field(default_factory=FrontendSettings)
    ingestion: IngestionSettings = Field(default_factory=IngestionSettings)


# ── Environment variable overrides ──────────────────────────────────

_ENV_OVERRIDES: list[tuple[str, list[str]]] = [
    ("PG_PASSWORD", ["database", "password"]),
    ("REDIS_PASSWORD", ["redis", "password"]),
    ("JWT_SECRET_KEY", ["auth", "local_fallback", "jwt_secret"]),
    ("SSO_CLIENT_SECRET", ["auth", "sso", "client_secret"]),
]


def _apply_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    """Override settings fields with environment variables when set."""
    for env_var, path in _ENV_OVERRIDES:
        value = os.environ.get(env_var)
        if value is not None:
            node = data
            for key in path[:-1]:
                node = node.setdefault(key, {})
            node[path[-1]] = value
    return data


def _resolve_env_placeholders(data: Any) -> Any:
    """Replace ${VAR} placeholders in string values with env vars."""
    if isinstance(data, str) and data.startswith("${") and data.endswith("}"):
        env_var = data[2:-1]
        return os.environ.get(env_var, "")
    if isinstance(data, dict):
        return {k: _resolve_env_placeholders(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_resolve_env_placeholders(v) for v in data]
    return data


# ── Required field validation ───────────────────────────────────────

_REQUIRED_FIELDS: list[str] = [
    "llm.primary.base_url",
    "llm.primary.model",
    "embedding.base_url",
    "vector_store.backend",
    "database.host",
    "redis.host",
]


def validate_settings(settings: Settings) -> None:
    """Validate that all required fields are present and non-empty.

    Raises:
        ValueError: with the field path of the first missing/empty field.
    """
    for field_path in _REQUIRED_FIELDS:
        obj: Any = settings
        for part in field_path.split("."):
            obj = getattr(obj, part, None)
            if obj is None:
                break
        if not obj:
            raise ValueError(f"Missing required setting: {field_path}")


# ── Loader ──────────────────────────────────────────────────────────

def load_settings(path: str = "config/settings.yaml") -> Settings:
    """Load settings from YAML, apply env overrides, validate, and return.

    Args:
        path: Path to the YAML config file.

    Returns:
        Validated Settings instance.

    Raises:
        FileNotFoundError: if the YAML file does not exist.
        ValueError: if a required field is missing.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Settings file not found: {path}")

    with open(config_path) as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    raw = _resolve_env_placeholders(raw)
    raw = _apply_env_overrides(raw)

    settings = Settings(**raw)
    validate_settings(settings)
    return settings
