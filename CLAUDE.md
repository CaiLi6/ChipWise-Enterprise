# CLAUDE.md

> This file is the single source of truth for AI assistant context. `.github/copilot-instructions.md` mirrors this content — keep both in sync when updating.

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ChipWise Enterprise** — a chip data intelligence retrieval and analysis platform for semiconductor hardware teams. Uses **Agentic RAG** (ReAct Agent + Tool Calling) and **Graph RAG** (Kùzu knowledge graph) for natural-language chip queries, comparisons, BOM review, and test case generation. All inference runs locally on a single AMD Ryzen AI 395 machine (128 GB RAM) via LM Studio (multi-model: primary reasoning model + lightweight router model) — zero data exfiltration.

**Status**: Documentation-driven Phase 1; source code is being built per `docs/DEVELOPMENT_PLAN.md`. Architecture spec lives in `docs/ENTERPRISE_DEV_SPEC.md` (v5.0, 7-chapter structure).

**Important**: Most `src/` paths referenced below don't exist yet. All are planned for Phase 1-6 per `DEVELOPMENT_PLAN.md`. If a file doesn't exist, check the plan to see which task creates it.

## Prerequisites

- **Python**: 3.10+ (async syntax, typing improvements)
- **Docker & Docker Compose**: For PostgreSQL, Milvus, Redis, microservices
- **LM Studio**: Must be installed and running separately at `http://localhost:1234/v1` with both a 35B primary model (Qwen-3-35B recommended) and a 1.7B router model (Qwen-3-1.7B recommended) loaded
- **Git**: For version control and branch workflows

Install Python dependencies (once code exists):
```bash
pip install -r requirements.txt
```

## Build & Run

```bash
# Infrastructure (PostgreSQL, Milvus, Redis)
docker-compose up -d

# Schema initialization
alembic upgrade head                    # or: python scripts/init_db.py
python scripts/init_milvus.py           # Milvus collections
python scripts/init_kuzu.py             # Kùzu knowledge graph

# Model microservices
docker-compose -f docker-compose.services.yml up -d   # BGE-M3 :8001, bce-reranker :8002

# LM Studio must be running separately at localhost:1234/v1 with primary + router models loaded
# (see config/settings.yaml llm.primary.model and llm.router.model)

# FastAPI gateway
uvicorn src.api.main:app --host 0.0.0.0 --port 8080

# Celery workers (3 queues)
celery -A src.ingestion.tasks worker -Q default,embedding -c 1 -n worker1@%h
celery -A src.ingestion.tasks worker -Q heavy -c 1 -n worker2@%h        # PaddleOCR
celery -A src.ingestion.tasks worker -Q crawler -c 1 -n worker3@%h
celery -A src.ingestion.tasks beat --loglevel=info

# Verify all services healthy
python scripts/healthcheck.py
```

## Tests

```bash
pytest -q                                        # All tests
pytest -q tests/unit/test_settings.py            # Single file
pytest -q -m unit                                # Unit only (no Docker)
pytest -q -m integration                         # Requires Docker infra
pytest -q tests/unit/test_smoke_imports.py       # Fast import smoke check
python -m compileall src                         # Syntax/import check
```

Markers: `unit`, `integration`, `e2e`, `load`. Load tests use `tests/load/locustfile.py`.

## Code Quality & Linting

```bash
# Type checking
mypy src                                        # Check all type annotations

# Linting & formatting
ruff check src tests                            # Check for violations
ruff format src tests                           # Auto-format code

# Test coverage
pytest --cov=src --cov-report=html              # Generate HTML coverage report
# Coverage targets: Libs ≥90%, Core ≥80%, API ≥70%, Overall ≥75% (per §5.1)

# Security scanning (GitHub Actions runs this in CI; local run optional)
python -m pip install bandit && bandit -r src   # Check for security issues
```

All code must pass `ruff check` and `mypy` before committing. Coverage is enforced in CI/CD (Phase 6).

## Development Workflow

**Git Flow** (per `ENTERPRISE_DEV_SPEC.md` §6.3):
- `main` — production-ready, released code
- `develop` — integration branch, features merged here first
- `feature/xxx` — individual feature branches off `develop`

**PR Process**:
1. Create feature branch: `git checkout -b feature/my-feature develop`
2. Implement + test + commit
3. Push to remote and create PR against `develop` (not `main`)
4. Require ≥1 reviewer approval + all CI checks pass
5. Squash-merge to `develop` (keeps history clean)
6. Release Manager merges `develop` → `main` at phase boundaries

**Commit Message Format**:
- Keep concise: "Add chip_compare tool" not "Added the chip comparison tool implementation"
- Reference task ID: "1A1: Create project skeleton" (references DEVELOPMENT_PLAN.md task 1A1)

## Troubleshooting

**"Connection refused" on port X**:
- Check `docker-compose ps` — is the service running?
- For LM Studio: ensure it's running separately in another terminal (`lm-studio` command)
- For PostgreSQL/Milvus/Redis: `docker-compose up -d` to start infrastructure

**"ModuleNotFoundError: No module named 'src...'"**:
- Ensure you're running commands from the project root directory
- If code paths don't exist, they haven't been implemented yet per DEVELOPMENT_PLAN.md

**LM Studio connection fails**:
- Verify LM Studio is running: `curl http://localhost:1234/v1/models`
- Verify models are loaded: check LM Studio UI at `http://localhost:1234`
- Verify `config/settings.yaml` has correct `llm.primary.model` and `llm.router.model` names

**Milvus or PostgreSQL exits immediately after `docker-compose up`**:
- Check logs: `docker-compose logs milvus` or `docker-compose logs postgres`
- Verify no port conflicts: check if ports 19530 (Milvus) or 5432 (Postgres) are already in use
- Verify disk space: both services need several GB

**Verify all services are healthy**:
```bash
python scripts/healthcheck.py  # Once code exists in Phase 1B
# Or manually: curl http://localhost:8080/readiness
```

## Architecture (7 Layers)

| Layer | Components |
|-------|-----------|
| 1 Frontend | Gradio (MVP) → Vue3 + Element Plus |
| 2 API Gateway | FastAPI :8080 — JWT, rate limiting, CORS |
| 3 Agent Orchestrator | ReAct loop (max 5 iterations), LLM-driven tool selection |
| 4 Core Services | QueryRewriter, ConversationManager, ResponseBuilder |
| 5 Model Services | LM Studio :1234 (primary + router models), BGE-M3 :8001, bce-reranker :8002 |
| 6 Storage | PostgreSQL :5432, Milvus :19530, Redis :6379, Kùzu (embedded) |
| 7 Libs | Pluggable: BaseLLM, BaseEmbedding, BaseVectorStore, BaseReranker, BaseGraphStore |

**Online flow**: HTTP → JWT + rate limit → GPTCache (cosine > 0.95) → ConversationManager → AgentOrchestrator (ReAct: Thought → Tool Calls → Observation → Final Answer) → ResponseBuilder

**Offline ingestion** (Celery chain): download → SHA256 dedup → PDF extract → 3-tier table extract → LLM param extract → chunk → embed → Milvus upsert → PG upsert → Kùzu graph sync

## Key Patterns

### Factory + Pluggable Abstractions
Every backend in `src/libs/` has `base.py` (abstract), an implementation, and `factory.py`. Switch backends via `config/settings.yaml` — no code changes. Pattern: `BaseLLM` → `LMStudioClient` → `LLMFactory._registry`. Factory creates separate client instances for `primary` and `router` roles based on `settings.yaml`.

```
src/libs/
  llm/          base.py  lmstudio_client.py  factory.py
  embedding/    base.py  bgem3_client.py     factory.py
  vector_store/ base.py  milvus_store.py     factory.py
  graph_store/  base.py  kuzu_store.py       factory.py
  reranker/     base.py  bce_client.py       factory.py
```

### Core Data Contracts (`src/core/types.py`)
Five types flow end-to-end — extend via subclasses, never break the base contracts:
- `Document` — ingested file metadata
- `Chunk` — text segment with position info
- `ChunkRecord` — Chunk + dense/sparse embedding vectors
- `ProcessedQuery` — rewritten query + conversation context + extracted entities
- `RetrievalResult` — ranked chunks with citations

### Agent Tools (`src/agent/tools/`)
Each tool inherits `BaseTool` (name, description, parameters_schema, execute). Auto-discovered by `ToolRegistry`. Adding a capability = new `BaseTool` subclass. Parallel tool calls enabled. Budget: 5 iterations, 8192 tokens max per request (`TokenBudget`).

### Kùzu Knowledge Graph
Runs **embedded** inside the FastAPI process (no port). Data dir: `data/kuzu/`. 6 node tables (Chip, Parameter, Errata, Document, DesignRule, Peripheral), 7 edge tables. Synced from PostgreSQL after every ingestion. Use openCypher via `conn.execute()`.

### Milvus Hybrid Search
BGE-M3 produces dense (1024-dim) + sparse vectors in one call. Use `collection.hybrid_search()` with `RRFRanker(k=60)`. HNSW: M=16, efConstruction=256, search ef=128.

### TraceContext
Every request gets a `trace_id`. Call `trace.record_stage(name, metadata)` in each processing step. Output: `logs/traces.jsonl`.

### Configuration

**settings.yaml** — `config/settings.yaml` controls all behavior. Reference schema in `docs/ENTERPRISE_DEV_SPEC.md` §7.1 (created in Phase 1A3). Key sections:
- `llm` — Primary (35B) and router (1.7B) model endpoints
- `embedding`, `reranker`, `vector_store`, `graph_store` — Backend implementations (Milvus, Kùzu, etc.)
- `agent`, `ingestion`, `cache`, `rate_limit`, `auth` — Feature config

**Secrets via environment variables** (override settings.yaml):
```bash
export PG_PASSWORD="your-postgres-password"
export REDIS_PASSWORD="your-redis-password"
export JWT_SECRET_KEY="your-jwt-signing-key"
export SSO_CLIENT_SECRET="your-oauth-client-secret"
```

Settings are validated on startup by `src/core/settings.py`. Missing required fields raise an error with the field path (e.g., `embedding.base_url`). For Phase 1 local development, you can use minimal values; Phase X deployment requires all secrets.

Key LM Studio config structure:
```yaml
llm:
  primary:                         # Main reasoning model
    provider: openai_compatible
    base_url: "http://localhost:1234/v1"
    model: "qwen3-35b-q5_k_m"      # any loaded LM Studio model
    api_key: "lm-studio"
  router:                          # Lightweight routing/rewrite model (1-3B)
    provider: openai_compatible
    base_url: "http://localhost:1234/v1"
    model: "qwen3-1.7b-q5_k_m"
    api_key: "lm-studio"
```

### Graceful Degradation
Optional components (Reranker, LLM enrichment, Graph, Cache) have `disabled`/`None` modes. Failures must not block the main path. `/readiness` returns `degraded` (not 500) when downstream services are unavailable.

### Prompt Templates
All LLM prompts live in `config/prompts/*.txt`. Reference by filename — do not hardcode prompts in Python.

## Redis Key Namespaces

- `session:{user_id}:{session_id}` — conversation (TTL 1800s, max 10 turns)
- `gptcache:query:*` / `gptcache:response:*` — semantic cache (TTL 3600-14400s)
- `ratelimit:{user_id}:minute/hour` — rate limits (max 30/min, 500/hr)
- `ratelimit:llm:semaphore` — global LLM concurrency (primary max 2, router max 10)
- `task:progress:{task_id}` — Celery task progress (TTL 86400s)
- DB 0: cache + sessions; DB 1: Celery broker

## Service Ports

FastAPI 8080 | LM Studio 1234 | BGE-M3 8001 | bce-reranker 8002 | PostgreSQL 5432 | Milvus 19530 | Redis 6379 | Kùzu embedded (no port) | Gradio 7860

## Celery Workers & Task Queue

The ingestion pipeline (Phase 3+) uses Celery for asynchronous document processing. Three worker pools handle different task types:

| Worker | Queue | Tasks | Notes |
|--------|-------|-------|-------|
| **worker1** | `default`, `embedding` | Download, dedup, extraction, chunking, embedding | Main ingestion tasks; normal CPU/memory |
| **worker2** | `heavy` | PaddleOCR (Tier 3 table extraction) | Loaded on-demand only; 3GB memory footprint; heavy CPU |
| **worker3** | `crawler` | Crawler fetch & parse (Playwright) | I/O bound; rate-limited per domain |
| **beat** | — | Scheduler | Triggers periodic crawler runs (2 AM daily per §7.1) |

**Configuration** (in Phase 1A):
- `task_acks_late=True` — ACK only after task completes; prevents data loss if worker crashes mid-task
- `worker_prefetch_multiplier=1` — Fair scheduling (one task per worker at a time, not 4x)
- Max retries: 3 with exponential backoff (2-60s range per §4.11.3)

**Monitor worker status**:
```bash
celery -A src.ingestion.tasks inspect active    # Running tasks
celery -A src.ingestion.tasks inspect reserved  # Queued tasks
```

## Project Phases Explained

ChipWise Enterprise is built in 6 phases over 16 weeks (78 total tasks in `DEVELOPMENT_PLAN.md`):

- **Phase 1 (Weeks 1-2)**: Infrastructure & skeleton — Docker, FastAPI gateway, database schema, Kùzu, Agent framework
- **Phase 2 (Weeks 3-4)**: Core Agentic RAG — Libs layer, Hybrid+Graph retrieval, Agent Orchestrator, 3 foundational tools
- **Phase 3 (Weeks 5-7)**: Data engineering — PDF extraction, parameter extraction, Celery pipeline, three ingestion sources
- **Phase 4 (Weeks 8-10)**: Structured tools — chip_compare, chip_select, bom_review (the "3 business tools")
- **Phase 5 (Weeks 11-13)**: Advanced features — test_case_gen, design_rule_check, knowledge_search, report_export (7 more tools)
- **Phase 6 (Weeks 14-16)**: Frontend & delivery — Gradio UI, SSO/OIDC, E2E testing, load testing, ops documentation

When you see "Phase X" or "future" in code comments, it means post-Phase-1 enhancement (Kubernetes deployment, cloud scaling, etc.).

## Key Documentation

**Architecture & Design**:
- `docs/ENTERPRISE_DEV_SPEC.md` — Full 7-chapter architecture specification with all technical decisions, data schemas, API endpoints, deployment topology. **Read this first to understand the system.**

**Execution & Tasks**:
- `docs/DEVELOPMENT_PLAN.md` — Phase-by-phase task breakdown (78 tasks). Each task lists files to create/modify, function signatures, acceptance criteria, and test methods. **Reference this to understand what to build in each phase.**

**Continuous Integration / Patterns**:
- `.github/copilot-instructions.md` — Mirrors this file; for GitHub Copilot users.

## Recent Changes

### 2026-04-09 — DEVELOPMENT_PLAN.md 对齐 §2.9/§2.10/§2.11 和 Phase X 标注

- 2C3 SafetyGuardrails → 新增 `StructuredOutputValidator` (§2.9) + `output_validator.py` + 测试
- 3A2 LLM 参数抽取 → 新增 Pydantic Schema 校验 + 领域规则约束 + `needs_review` 标记
- 6A3 监控仪表盘 → 新增 Token 用量追踪面板 (§2.11) + `TokenTracker` + Prometheus metrics
- 6C2 安全审计 → 新增 GitHub Code Scanning (CodeQL) 配置 + `security-scan.yaml`
- 6D2 部署运维文档 → 新增 CI/CD 工具说明 + Token 监控说明 + 内存峰值告警
- 版本引用更新至 2026-04-09（含 §2.9-2.11 新增章节）

### 2026-04-09 — ENTERPRISE_DEV_SPEC.md §4-§7 一致性传播

**SonarQube Phase X 传播（5 处）**:
- §4.1 L634 横切关注点图: SonarQube → Ruff+GitHub Scanning+Trivy
- §4.4 L1500 目录结构注释: 明确 Phase 1 vs Phase X 工具分工
- §5.6 CI/CD YAML: sonarSource action → GitHub CodeQL (Phase 1), SonarQube 注释为 Phase X
- §5.7 质量门: 拆分 Phase 1 (Ruff+mypy+CodeQL) 与 Phase X (SonarQube) 两套标准
- §7 术语表: SonarQube 加注 "(Phase X 可选)"

**§2.9 结构化输出校验传播（2 处）**:
- §4.3 STEP 5 参数抽取: 新增 Pydantic Schema 校验 + 领域规则约束
- §4.8.1 Safety Guardrails 图: 新增 Structured Output Validator

**§2.10/§2.11 指标传播（3 处）**:
- §5.2 RAG 质量指标: 新增 NDCG@10/EM/F1/Schema 校验通过率 + §2.10 交叉引用
- §5.5 监控面板: 新增 Token 用量追踪面板 (§2.11)
- §5.5 告警阈值: 新增内存利用率、Schema 校验失败率、Token 日用量告警

### 2026-04-09 — ENTERPRISE_DEV_SPEC.md §2/§3 优化

**§1.2 关键技术能力表修正**:
- 移除未使用的 "Qdrant" 引用 → 统一为 Milvus Standalone / Cluster
- 部署方式描述改为 "Docker Compose (Phase 1) → Helm + K8s (Phase X)"

**§2 核心特点新增**:
- §2.9 结构化输出校验（Pydantic Schema + 领域规则约束 + Phase 2 Outlines 受限解码）
- §2.10 RAG 质量评估（NDCG@10 / EM/F1 / 黄金测试集 / 自动化基准）
- §2.11 Token 用量追踪（Prometheus metrics + Grafana 面板）
- §2.5 GPTCache 加注 Phase 2 迁移至自研语义缓存
- §2.4 三级 PDF 提取加注 Phase 3 评估 Docling 替代 Camelot
- §2.8 CI/CD 图更新: SonarQube → GitHub Scanning, helm → Phase X

**§3 技术选型优化**:
- §3.1 PostgreSQL shared_buffers 1GB → 2GB; 新增峰值内存风险提示 + Celery 暂停策略
- §3.3 Embedding/Reranker 加注 Phase 2 迁移路线图 (Jina v3 / jina-reranker-v2)
- §3.5 Celery 加注 Phase 2 评估 Dramatiq/Huey
- §3.7 SonarQube 标注 Phase X 可选; Helm 标注 Phase X; 新增 Ruff+mypy+GitHub Code Scanning

### 2026-04-09 — DEVELOPMENT_PLAN.md 完善

**格式对齐 `docs/template.md`**：
- 顶部添加统一**排期原则**（5 条原则）+ **阶段总览表**（6 Phase，总计 77 任务）
- 全部 6 个 Phase 进度跟踪表**集中到顶部**（删除原来散落在各 Phase 内的重复表）
- 添加 **📈 总体进度** 汇总表（各 Phase 任务数/已完成/百分比）
- Phase 1 补齐正式标题 `### Phase 1: Infrastructure & Skeleton (Week 1-2)` + 子排期原则
- 文末添加**交付里程碑**表（M1-M6）

**内容对齐 `docs/ENTERPRISE_DEV_SPEC.md` v5.0**：
- 修正 `第 2.4 节` → `§4.4`
- Task 2A4 全面更新：`Lemonade LLM Client` → `LMStudio LLM Client`（文件名 `lmstudio_client.py`、类名 `LMStudioClient`、端口 `:8000` → `:1234`、URL `http://localhost:1234/v1`、测试文件名）
- 1A1 + 1A3 `settings.yaml` 配置段补齐 `graph_store`、`agent` 段
- 6D2 部署文档：`Lemonade Server` → `LM Studio`

### 2026-04-08 — ENTERPRISE_DEV_SPEC.md §4.4 更新

将 §4.4 项目目录结构从约 100 行简略树形图扩展为 ~374 行完整注释目录树，覆盖规格书所有章节引用的文件（含 10 个 Agent Tools、6 条 Pipelines、所有脚本、测试结构、部署配置等）。
