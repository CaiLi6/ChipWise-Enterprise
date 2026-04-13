# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> `.github/copilot-instructions.md` mirrors this file — keep both in sync when updating.

## Project Overview

**ChipWise Enterprise** — a chip data intelligence retrieval and analysis platform for semiconductor hardware teams. Uses **Agentic RAG** (ReAct Agent + Tool Calling) and **Graph RAG** (Kùzu knowledge graph) for natural-language chip queries, comparisons, BOM review, and test case generation. All inference runs locally on a single AMD Ryzen AI 395 machine (128 GB RAM) via LM Studio — zero data exfiltration.

All 6 development phases are complete. Architecture spec: `docs/ENTERPRISE_DEV_SPEC.md` (v5.0). Task breakdown: `docs/DEVELOPMENT_PLAN.md` (78 tasks).

## Prerequisites

- **Python 3.10+**, **Docker & Docker Compose**, **Git**
- **LM Studio**: running separately at `http://localhost:1234/v1` with a 35B primary model and 1.7B router model loaded

```bash
pip install -r requirements.txt
```

## Build & Run

```bash
# Infrastructure (PostgreSQL, Milvus, Redis)
docker-compose up -d

# Schema initialization
alembic upgrade head
python scripts/init_milvus.py
python scripts/init_kuzu.py

# Model microservices (BGE-M3 :8001, bce-reranker :8002)
docker-compose -f docker-compose.services.yml up -d

# FastAPI gateway
uvicorn src.api.main:app --host 0.0.0.0 --port 8080

# Celery workers (3 queues)
celery -A src.ingestion.tasks worker -Q default,embedding -c 1 -n worker1@%h
celery -A src.ingestion.tasks worker -Q heavy -c 1 -n worker2@%h        # PaddleOCR
celery -A src.ingestion.tasks worker -Q crawler -c 1 -n worker3@%h
celery -A src.ingestion.tasks beat --loglevel=info

# Verify all services healthy
python scripts/healthcheck.py
# Or: curl http://localhost:8080/readiness
```

## Tests

```bash
pytest -q                                        # All tests
pytest -q tests/unit/test_settings.py            # Single file
pytest -q -m unit                                # Unit only (no Docker)
pytest -q -m integration                         # Requires Docker infra
pytest -q tests/unit/test_smoke_imports.py       # Fast import smoke check
python -m compileall src                         # Syntax check
```

Markers: `unit`, `integration`, `e2e`, `load`. `asyncio_mode = "auto"` (pytest-asyncio) — async tests need no decorator. Integration tests assume Docker services are healthy. Load tests use `tests/load/locustfile.py`.

**FastAPI unit tests** use `app.dependency_overrides` to mock auth and the orchestrator without a real JWT or LM Studio:
```python
app.dependency_overrides[get_current_user] = lambda: _TEST_USER
app.dependency_overrides[get_orchestrator] = lambda: mock_orch
```

## Code Quality & Linting

```bash
ruff check src tests        # Lint (line-length 120, rules: E/F/W/I/N/UP/B/A/SIM)
ruff format src tests       # Format
mypy src                    # Type check
pytest --cov=src --cov-report=html   # Coverage (targets: Libs ≥90%, Core ≥80%, API ≥70%)
```

All code must pass `ruff check` and `mypy` before committing.

## Architecture (7 Layers)

| Layer | Components |
|-------|-----------|
| 1 Frontend | Gradio MVP (`frontend/`) → Vue3 + Element Plus (production) |
| 2 API Gateway | FastAPI :8080 — JWT, rate limiting, CORS, request tracing |
| 3 Agent Orchestrator | ReAct loop (max 5 iterations), LLM-driven tool selection |
| 4 Core Services | QueryRewriter, ConversationManager, ResponseBuilder, ReportEngine |
| 5 Model Services | LM Studio :1234 (primary + router models), BGE-M3 :8001, bce-reranker :8002 |
| 6 Storage | PostgreSQL :5432, Milvus :19530, Redis :6379, Kùzu (embedded) |
| 7 Libs | Pluggable: BaseLLM, BaseEmbedding, BaseVectorStore, BaseReranker, BaseGraphStore |

**Online flow**: HTTP → JWT + rate limit → SemanticCache (cosine > 0.95) → ConversationManager → AgentOrchestrator (ReAct: Thought → Tool Calls → Observation → Final Answer) → ResponseBuilder

**Offline ingestion** (Celery chain): download → SHA256 dedup → PDF extract → 3-tier table extract → LLM param extract → chunk → embed → Milvus upsert → PG upsert → Kùzu graph sync

## API Routers (`src/api/routers/`)

All registered in `src/api/main.py`:

| Router | Prefix | Purpose |
|--------|--------|---------|
| `health` | `/health`, `/readiness`, `/liveness` | Health checks |
| `auth` | `/api/v1/auth` | Local JWT login/refresh |
| `sso` | `/api/v1/auth/sso` | OIDC login redirect + callback (Keycloak/DingTalk/Feishu) |
| `query` | `/api/v1/query` | Standard + SSE streaming query (wires to AgentOrchestrator) |
| `compare` | `/api/v1/compare` | Chip comparison endpoint |
| `documents` | `/api/v1/documents` | Document upload |
| `tasks` | `/api/v1/tasks` | Celery task status + WebSocket push |
| `knowledge` | `/api/v1/knowledge` | Knowledge graph CRUD |

The query router creates the `AgentOrchestrator` as a **lazy module-level singleton** (`_orchestrator_initialized` flag). It returns `None` when LM Studio is unavailable; endpoints return HTTP 503 gracefully.

## Key Patterns

### Factory + Pluggable Abstractions

Every backend in `src/libs/` has `base.py` (abstract), an implementation, and `factory.py`. Switch backends via `config/settings.yaml` — no code changes. `LLMFactory` creates separate instances for `primary` (35B) and `router` (1.7B) roles.

```
src/libs/
  llm/          base.py  lmstudio_client.py  factory.py
  embedding/    base.py  bgem3_client.py     factory.py
  vector_store/ base.py  milvus_store.py     factory.py
  graph_store/  base.py  kuzu_store.py       factory.py
  reranker/     base.py  bce_client.py       factory.py
```

### Core Data Contracts (`src/core/types.py`)

Five types flow end-to-end — extend via subclasses, never break the base:
- `Document` — ingested file metadata
- `Chunk` — text segment with position info
- `ChunkRecord` — Chunk + dense/sparse embedding vectors
- `ProcessedQuery` — rewritten query + conversation context + extracted entities
- `RetrievalResult` — ranked chunks with citations

### Agent Tools (`src/agent/tools/`)

Each tool inherits `BaseTool` (name, description, parameters_schema, execute). Auto-discovered by `ToolRegistry.discover()`. Adding a capability = new `BaseTool` subclass. Parallel tool calls enabled. Budget: 5 iterations, 8192 tokens max (`TokenBudget`).

Implemented tools: `rag_search`, `graph_query`, `sql_query`, `chip_compare`, `chip_select`, `bom_review`, `test_case_gen`, `design_rule`, `knowledge_search`, `report_export`.

### Kùzu Knowledge Graph

Runs **embedded inside the FastAPI process** (no port). Data dir: `data/kuzu/`. Schema: 6 node tables (Chip, Parameter, Errata, Document, DesignRule, Peripheral), 7 edge tables. Synced from PostgreSQL after every ingestion. Use openCypher via `conn.execute()`.

### Milvus Hybrid Search

BGE-M3 produces dense (1024-dim) + sparse vectors in one call. Use `collection.hybrid_search()` with `RRFRanker(k=60)`. HNSW: M=16, efConstruction=256, search ef=128.

### SSO/OIDC Authentication (`src/auth/sso/`)

Three providers: `KeycloakProvider`, `DingTalkProvider`, `FeishuProvider` — all inherit `BaseSSOProvider`. CSRF state stored in-memory (`_STATE_STORE` dict, 600s TTL; use Redis in production). `JITProvisioner` creates/updates local users on first login with priority-based role mapping (admin > user > viewer). Flow: `/login` → IdP redirect (state+nonce) → `/callback` → code exchange → JIT provision → issue ChipWise JWT.

### TraceContext

Every request gets a `trace_id` (from `X-Request-ID` header or auto-generated). Call `trace.record_stage(name, metadata)` in each processing step. Output: `logs/traces.jsonl`. Import from `src/observability/trace_context.py`.

### Configuration

`config/settings.yaml` controls all behavior. Validated on startup by `src/core/settings.py`; missing required fields raise an error with the field path. Secrets override via env vars:
```bash
export PG_PASSWORD="..."
export REDIS_PASSWORD="..."
export JWT_SECRET_KEY="..."
export SSO_CLIENT_SECRET="..."
```

Key LM Studio config:
```yaml
llm:
  primary:
    provider: openai_compatible
    base_url: "http://localhost:1234/v1"
    model: "qwen3-35b-q5_k_m"
    api_key: "lm-studio"
  router:
    provider: openai_compatible
    base_url: "http://localhost:1234/v1"
    model: "qwen3-1.7b-q5_k_m"
    api_key: "lm-studio"
```

All LLM prompts live in `config/prompts/*.txt` — reference by filename, never hardcode in Python.

### Graceful Degradation

Optional components (Reranker, Graph, Cache, AgentOrchestrator) have `disabled`/`None` modes. Failures must not block the main path. `/readiness` returns `degraded` (not 500) when downstream services are unavailable.

## Redis Key Namespaces

- `session:{user_id}:{session_id}` — conversation (TTL 1800s, max 10 turns)
- `gptcache:query:*` / `gptcache:response:*` — semantic cache (TTL 3600–14400s)
- `ratelimit:{user_id}:minute/hour` — rate limits (max 30/min, 500/hr)
- `ratelimit:llm:semaphore` — global LLM concurrency (primary max 2, router max 10)
- `task:progress:{task_id}` — Celery task progress (TTL 86400s)
- DB 0: cache + sessions; DB 1: Celery broker

## Celery Workers

| Worker | Queue | Notes |
|--------|-------|-------|
| worker1 | `default`, `embedding` | Main ingestion tasks |
| worker2 | `heavy` | PaddleOCR (3 GB footprint, loaded on-demand) |
| worker3 | `crawler` | Playwright crawler, rate-limited per domain |
| beat | — | Periodic crawler runs (2 AM daily) |

Config: `task_acks_late=True`, `worker_prefetch_multiplier=1`, max 3 retries with exponential backoff (2–60s).

## Service Ports

FastAPI 8080 | LM Studio 1234 | BGE-M3 8001 | bce-reranker 8002 | PostgreSQL 5432 | Milvus 19530 | Redis 6379 | Kùzu embedded (no port) | Gradio 7860

## Troubleshooting

**"Connection refused" on port X**: Check `docker-compose ps`. For LM Studio: `curl http://localhost:1234/v1/models`.

**"ModuleNotFoundError: No module named 'src...'"**: Run commands from the project root directory.

**Milvus/PostgreSQL exits immediately**: Check `docker-compose logs milvus` / `docker-compose logs postgres` for port conflicts or disk space.
