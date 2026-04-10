# ChipWise Enterprise — Copilot Instructions

> **同步说明**: 本文件与项目根目录 `CLAUDE.md` 内容基本一致。修改时请同步更新两份文件。最近同步版本: ENTERPRISE_DEV_SPEC v5.0 (2026-04-09)。

**ChipWise Enterprise** is a chip data intelligence retrieval and analysis platform for semiconductor hardware teams. It uses **Agentic RAG** (ReAct Agent + Tool Calling) and **Graph RAG** (Kùzu knowledge graph) to provide natural-language chip parameter queries, comparisons, BOM review, and test case generation. All compute runs locally on a single AMD Ryzen AI 395 machine (128 GB RAM, LM Studio for multi-model inference (primary reasoning model + lightweight router model)).

---

## Build & Run

```bash
# Start infrastructure (PostgreSQL, Milvus, Redis)
docker-compose up -d

# Initialize PostgreSQL schema
alembic upgrade head
# or: python scripts/init_db.py

# Initialize Milvus collections
python scripts/init_milvus.py

# Initialize Kùzu knowledge graph
python scripts/init_kuzu.py

# Start model microservices (BGE-M3 :8001, bce-reranker :8002)
docker-compose -f docker-compose.services.yml up -d

# Start FastAPI gateway (port 8080)
uvicorn src.api.main:app --host 0.0.0.0 --port 8080

# Start Celery workers
celery -A src.ingestion.tasks worker -Q default,embedding -c 1 -n worker1@%h
celery -A src.ingestion.tasks worker -Q heavy -c 1 -n worker2@%h
celery -A src.ingestion.tasks worker -Q crawler -c 1 -n worker3@%h
celery -A src.ingestion.tasks beat --loglevel=info

# Health check all services
python scripts/healthcheck.py
```

LM Studio must be running separately at `http://localhost:1234/v1` with both the primary reasoning model and router model loaded (configured in `config/settings.yaml` under `llm.primary.model` and `llm.router.model`).

---

## Tests

```bash
# All tests
pytest -q

# Single test file
pytest -q tests/unit/test_settings.py

# Unit tests only (no Docker required)
pytest -q -m unit

# Integration tests (requires Docker infra running)
pytest -q -m integration

# Smoke import check
pytest -q tests/unit/test_smoke_imports.py

# Syntax/importability check only
python -m compileall src
```

Test markers: `unit`, `integration`, `e2e`, `load`. Integration tests assume Docker services are healthy. `load/locustfile.py` is used for 20-user concurrency testing.

---

## Architecture Overview

Seven-layer architecture:

| Layer | Components |
|-------|-----------|
| **1 Frontend** | Gradio (MVP) → Vue3 + Element Plus (production) |
| **2 API Gateway** | FastAPI :8080 — JWT auth, rate limiting, CORS, request logging |
| **3 Agent Orchestrator** | ReAct/Tool-Calling loop (max 5 iterations); LLM selects tools dynamically |
| **4 Core Services** | QueryRewriter, ConversationManager, ResponseBuilder, ReportEngine |
| **5 Model Services** | LM Studio :1234 (主推理模型 + 路由模型), BGE-M3 :8001, bce-reranker :8002 |
| **6 Storage** | PostgreSQL :5432, Milvus :19530, Redis :6379, Kùzu (embedded) |
| **7 Libs** | Pluggable abstractions: BaseLLM, BaseEmbedding, BaseVectorStore, BaseReranker, BaseGraphStore |

### Online Request Flow

```
HTTP Request → FastAPI (JWT + rate limit) → GPTCache (cosine > 0.95 → cache hit)
→ ConversationManager (load Redis session, QueryRewriter for coreference)
→ AgentOrchestrator (ReAct loop: Thought → Tool Calls → Observation → repeat or Final Answer)
→ ResponseBuilder (format + citations + write cache + update session)
→ Return to user
```

### Offline Ingestion Flow

Celery task chain: `download → SHA256 dedup → PDF text extraction → 3-tier table extraction → LLM param extraction → chunking → BGE-M3 embed → Milvus upsert → PostgreSQL upsert → Kùzu graph sync → notify`

Three ingestion sources: Playwright crawler (scheduled), Watchdog directory monitor, manual REST upload.

---

## Key Conventions

### Pluggable Abstractions + Factory Pattern

Every backend component has a `Base*` abstract class and a `*Factory` with a `_registry` dict. Switch implementations by changing `config/settings.yaml` — no code changes required.

```
src/libs/
  llm/          base.py  lmstudio_client.py  factory.py
  embedding/    base.py  bgem3_client.py     factory.py
  vector_store/ base.py  milvus_store.py     factory.py
  graph_store/  base.py  kuzu_store.py       factory.py
  reranker/     base.py  bce_client.py       factory.py
```

### Core Data Contracts (`src/core/types.py`)

Five types flow through the entire pipeline — extend via subclasses, never break the base:
- `Document` — ingested file metadata
- `Chunk` — text segment with position info
- `ChunkRecord` — Chunk + embedding vectors
- `ProcessedQuery` — rewritten query + conversation context
- `RetrievalResult` — ranked chunks with citations

### TraceContext

Every request gets a unique `trace_id`. Each stage calls `trace.record_stage(stage_name, metadata)`. Stored in `logs/traces.jsonl`. Use `TraceContext` from `src/observability/trace_context.py` for all new request paths.

### Configuration

All behavior is controlled by `config/settings.yaml`. Sensitive fields are overridable via environment variables (`PG_PASSWORD`, `REDIS_URL`, `JWT_SECRET_KEY`). Settings are validated on startup via `src/core/settings.py`; missing required fields raise an error with the field path (e.g., `embedding.base_url`).

```yaml
# LM Studio connection (OpenAI-compatible, multi-model)
llm:
  primary:                         # Main reasoning model
    provider: openai_compatible
    base_url: "http://localhost:1234/v1"
    model: "qwen3-35b-q5_k_m"      # Example; any loaded LM Studio model
    api_key: "lm-studio"
  router:                          # Lightweight routing model
    provider: openai_compatible
    base_url: "http://localhost:1234/v1"
    model: "qwen3-1.7b-q5_k_m"     # Example; 1-3B class
    api_key: "lm-studio"
```

### Agent Tools

Each tool in `src/agent/tools/` inherits `BaseTool` and is auto-discovered by `ToolRegistry`. Adding a new capability = write a new `BaseTool` subclass. The Agent calls tools in parallel when possible (`parallel_tool_calls: true`). Max 5 ReAct iterations and 8192 tokens per request (enforced by `TokenBudget`).

### Kùzu Knowledge Graph

Kùzu runs **embedded inside the FastAPI process** (no separate service/port). Data directory: `data/kuzu/`. Schema: 6 node tables (`Chip`, `Parameter`, `Errata`, `Document`, `DesignRule`, `Peripheral`) and 7 edge tables. Use openCypher via `conn.execute()`. Graph is synced from PostgreSQL at the end of every ingestion task chain.

### Milvus Hybrid Search

BGE-M3 produces both dense (1024-dim) and sparse vectors in a single call. Use `collection.hybrid_search()` with `RRFRanker(k=60)` — no manual BM25 or RRF code. HNSW index: `M=16, efConstruction=256`. Search: `ef=128`.

### Redis Key Namespaces

- `session:{user_id}:{session_id}` — conversation history (TTL 1800s, max 10 turns)
- `gptcache:*` — semantic cache entries (TTL 3600–14400s)
- `ratelimit:{user_id}:minute/hour` — rate limit counters
- `task:progress:{task_id}` — Celery task progress (TTL 86400s)
- DB 0: app cache + sessions; DB 1: Celery broker + result backend

### Celery Configuration

- `task_acks_late=True` — task is ACKed only after completion (prevents data loss on worker crash)
- `worker_prefetch_multiplier=1` — fair scheduling
- Queue routing: `heavy` (PaddleOCR), `embedding`, `crawler`, `default`
- PaddleOCR is loaded on-demand in `heavy` workers only

### Graceful Degradation

Each optional component (Reranker, LLM enrichment, Graph sync) has a `disabled`/`None` mode. Failures in optional components must not block the main request path. The `/readiness` endpoint returns `degraded` (not 500) when downstream services are unavailable.

### Prompt Templates

All LLM prompts live in `config/prompts/` as `.txt` files. Reference by filename in code — do not hardcode prompt strings in Python.

### Service Ports

| Service | Port |
|---------|------|
| FastAPI Gateway | 8080 |
| LM Studio (LLM) | 1234 |
| BGE-M3 Embedding | 8001 |
| bce-reranker | 8002 |
| PostgreSQL | 5432 |
| Milvus | 19530 |
| Redis | 6379 |
| Kùzu | embedded (no port) |
| Gradio Frontend | 7860 |

---

## Recent Changes

### 2026-04-09 — DEVELOPMENT_PLAN.md 对齐 §2.9/§2.10/§2.11 和 Phase X 标注

2C3 新增 StructuredOutputValidator (§2.9)；3A2 新增 Pydantic Schema 校验 + 领域规则；6A3 新增 Token 追踪面板 (§2.11) + TokenTracker；6C2 新增 GitHub Code Scanning (CodeQL) 配置；6D2 新增 CI/CD 工具说明 + Token 监控 + 内存告警；版本引用更新至 2026-04-09。

### 2026-04-09 — ENTERPRISE_DEV_SPEC.md §4-§7 一致性传播

SonarQube Phase X 传播（5 处: §4.1 横切图、§4.4 目录注释、§5.6 CI/CD YAML、§5.7 质量门、§7 术语表）。§2.9 结构化校验传播（§4.3 STEP 5 加 Pydantic 校验、§4.8.1 Guardrails 图加 Output Validator）。§2.10/§2.11 指标传播（§5.2 补 NDCG@10/EM/F1/Schema 通过率、§5.5 监控面板加 Token 追踪、告警加内存/Schema/Token 阈值）。

### 2026-04-09 — ENTERPRISE_DEV_SPEC.md §2/§3 优化

§1.2 修正 Qdrant/Helm 不一致描述。§2 新增 2.9 结构化输出校验、2.10 RAG 质量评估、2.11 Token 用量追踪；§2.5 GPTCache 加注自研迁移路线；§2.4 PDF 加注 Docling 评估。§3 优化: PG shared_buffers 1→2GB + 峰值策略；§3.3 加注 Jina v3/jina-reranker-v2 迁移路线；§3.5 加注 Dramatiq/Huey 评估；§3.7 SonarQube→Phase X，新增 Ruff/mypy/GitHub Scanning。

### 2026-04-09 — DEVELOPMENT_PLAN.md 完善

格式对齐 `docs/template.md`：顶部添加排期原则 + 阶段总览表 + 集中进度跟踪表（6 Phase）+ 总体进度汇总 + 交付里程碑（M1-M6）。内容对齐 DEV_SPEC v5.0：修正 §4.4 引用、2A4 全面从 Lemonade → LMStudio（`lmstudio_client.py`，:1234）、settings.yaml 补齐 `graph_store`/`agent` 段。

### 2026-04-08 — ENTERPRISE_DEV_SPEC.md §4.4 更新

§4.4 项目目录结构从 ~100 行扩展为 ~374 行完整注释目录树，覆盖所有章节引用的文件。
