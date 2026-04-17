# ChipWise Enterprise — 12-Chapter Learning Syllabus

## Course Overview

ChipWise Enterprise 是一个芯片数据智能检索分析平台，使用 Agentic RAG + Graph RAG 架构，所有推理在本地 LM Studio 上运行。本课程带你从全局到细节掌握整个系统。

**Prerequisites**: Python 基础, 了解 REST API, 对数据库有基本概念

**Learning Path**:
```
Overview → API Layer → Agent Brain → Retrieval Engine → Storage → Ingestion Pipeline
    → Model Services → Auth → Core Libs → Frontend → Testing → Deployment
```

---

## Chapter 1: Project Overview & Architecture (入门全景)

**Learning Objectives**:
- Understand what ChipWise Enterprise solves and for whom
- Map the 7-layer architecture in your head
- Trace a query from HTTP request to final response

**Key Files**:
- `CLAUDE.md` — Project bible
- `docs/ENTERPRISE_DEV_SPEC.md` §1-§2 — Overview & core features
- `config/settings.yaml` — All configuration in one file

**Key Concepts**: 7-layer architecture, Agentic RAG, Graph RAG, local inference (LM Studio)

**Quiz Focus**: Architecture layers, data flow, why local inference

---

## Chapter 2: API Gateway (FastAPI 网关层)

**Learning Objectives**:
- Understand how HTTP requests enter the system
- Know all router endpoints and their purposes
- Understand middleware chain: JWT → rate limit → CORS → tracing

**Key Files**:
- `src/api/main.py` — App factory, router registration, lifespan
- `src/api/routers/` — All 8 routers (health, auth, sso, query, compare, documents, tasks, knowledge)
- `src/api/dependencies.py` — Dependency injection container
- `src/api/middleware/` — Rate limiting, CORS, request tracing

**Key Concepts**: FastAPI Depends, lazy singleton, graceful degradation (503), lifespan events

**Quiz Focus**: Router registration, dependency injection pattern, why orchestrator can be None

---

## Chapter 3: Agent Orchestrator (ReAct 智能体)

**Learning Objectives**:
- Understand the ReAct loop: Thought → Tool Call → Observation → Final Answer
- Know how tools are discovered and registered
- Understand token budget and iteration limits

**Key Files**:
- `src/agent/orchestrator.py` — Core ReAct loop
- `src/agent/tool_registry.py` — Auto-discovery + registration
- `src/agent/tools/base_tool.py` — BaseTool ABC
- `src/agent/tools/rag_search.py` — Most important tool implementation
- `src/agent/token_budget.py` — Budget tracking

**Key Concepts**: ReAct pattern, tool calling, auto-discovery via `pkgutil`, OpenAI function-calling schema, parallel tool calls

**Quiz Focus**: How does the agent decide which tool to use? What happens at iteration 5? How to add a new tool?

---

## Chapter 4: Retrieval Engine (检索引擎)

**Learning Objectives**:
- Understand hybrid search: dense + sparse + RRF fusion
- Know the difference between BGE-M3 sparse and Milvus BM25
- Understand the multi-source fusion pipeline: vector + SQL + graph

**Key Files**:
- `src/retrieval/hybrid_search.py` — Dense+Sparse hybrid with bgem3/bm25 switch
- `src/retrieval/reranker.py` — CoreReranker with fallback
- `src/retrieval/graph_search.py` — Kuzu graph traversal
- `src/retrieval/sql_search.py` — PostgreSQL fallback search
- `src/retrieval/fusion.py` — Multi-source weighted fusion

**Key Concepts**: RRFRanker, sparse_method config, Graph Boost, degradation chain, rerank pipeline

**Quiz Focus**: When does dense-only fallback trigger? How does RRF fusion work? BGE-M3 sparse vs BM25 trade-offs

---

## Chapter 5: Storage Layer (存储层)

**Learning Objectives**:
- Understand 4 storage engines and their responsibilities
- Know the Milvus collection schema and index strategy
- Understand Redis key namespaces and TTL strategy
- Read Kuzu graph schema (nodes + edges)

**Key Files**:
- `src/libs/vector_store/milvus_store.py` — Milvus operations
- `src/libs/graph_store/kuzu_store.py` — Kuzu operations
- `scripts/init_milvus.py` — Collection schema + BM25 function
- `scripts/init_kuzu.py` — Graph schema (6 nodes, 7 edges)
- `alembic/` — PostgreSQL migrations

**Key Concepts**: Factory pattern for all backends, HNSW vs SPARSE_INVERTED_INDEX, embedded graph DB, Redis DB 0 vs DB 1

**Quiz Focus**: Why 4 databases instead of 1? What does each index type optimize for? How does Kuzu sync from PG?

---

## Chapter 6: Ingestion Pipeline (离线入库流水线)

**Learning Objectives**:
- Trace the full Celery chain: download → dedup → extract → chunk → embed → store → graph sync
- Understand 3-tier PDF table extraction
- Know the 5 chunking strategies and when to use each

**Key Files**:
- `src/ingestion/tasks.py` — Celery task definitions
- `src/ingestion/pdf_extractor.py` — 3-tier extraction (pdfplumber → camelot → PaddleOCR)
- `src/ingestion/chunking/` — All chunkers + factory
- `src/ingestion/graph_sync.py` — PG → Kuzu sync
- `src/ingestion/dedup.py` — SHA256 deduplication

**Key Concepts**: Celery chain, task_acks_late, 3 worker queues (default/heavy/crawler), exponential backoff, SHA256 dedup

**Quiz Focus**: Why separate queue for PaddleOCR? What happens if embedding service is down mid-pipeline? How does parent-child chunking work?

---

## Chapter 7: Model Services (模型服务层)

**Learning Objectives**:
- Understand LM Studio dual-model setup (primary 35B + router 1.7B)
- Know BGE-M3 embedding service API and output format
- Understand factory pattern for swappable backends

**Key Files**:
- `src/libs/llm/base.py` + `lmstudio_client.py` + `factory.py` — LLM abstraction
- `src/libs/embedding/base.py` + `bgem3_client.py` + `factory.py` — Embedding abstraction
- `src/libs/reranker/base.py` + `bce_client.py` + `factory.py` — Reranker abstraction
- `src/services/embedding_service.py` — BGE-M3 FastAPI microservice
- `config/prompts/` — All LLM prompts (never hardcoded)

**Key Concepts**: Factory + Registry pattern, primary vs router role, EmbeddingResult (dense + sparse), prompt files separation

**Quiz Focus**: Why two LLM models? How does LLMFactory know which model to create? What does return_sparse=False do?

---

## Chapter 8: Authentication (认证鉴权)

**Learning Objectives**:
- Understand SSO/OIDC flow: login → IdP redirect → callback → JIT provision → JWT
- Know the 3 SSO providers and their differences
- Understand local fallback auth for development

**Key Files**:
- `src/auth/sso/base.py` — BaseSSOProvider ABC
- `src/auth/sso/keycloak.py`, `dingtalk.py`, `feishu.py` — Provider implementations
- `src/auth/sso/state_store.py` — Redis CSRF state (SETEX/GETDEL)
- `src/auth/sso/jit_provisioner.py` — First-login user creation
- `src/api/routers/auth.py` — Local JWT auth router
- `src/api/routers/sso.py` — SSO router

**Key Concepts**: OIDC code flow, CSRF state in Redis, JIT provisioning, priority role mapping, RS256 JWT

**Quiz Focus**: Why store CSRF state in Redis not memory? What is JIT provisioning? How does role mapping priority work?

---

## Chapter 9: Core Libraries (核心基础库)

**Learning Objectives**:
- Understand the settings system: YAML → Pydantic → env overrides
- Know the 5 core data types that flow through the entire system
- Understand observability: TraceContext, structured logging
- Know resilience patterns: circuit breaker, retry, rate limit

**Key Files**:
- `src/core/settings.py` — Settings loader + validation
- `src/core/types.py` — Document, Chunk, ChunkRecord, ProcessedQuery, RetrievalResult
- `src/observability/trace_context.py` — Request tracing
- `config/settings.yaml` — The one config to rule them all

**Key Concepts**: Single YAML config, env var overrides, Pydantic validation, trace_id propagation, data contract discipline

**Quiz Focus**: How do env vars override YAML? What fields does ProcessedQuery carry? How does trace_id flow through the system?

---

## Chapter 10: Frontend (前端层)

**Learning Objectives**:
- Understand Gradio MVP vs Vue3 production app
- Know Vue3 app structure: Vite + Element Plus + Pinia
- Understand API integration patterns

**Key Files**:
- `frontend/gradio_app.py` — Gradio MVP (deprecated)
- `frontend/web/src/` — Vue3 app source
- `frontend/web/src/stores/` — Pinia state management
- `frontend/web/src/views/` — Page components

**Key Concepts**: Gradio for prototyping, Vue3 + Element Plus for production, Pinia stores, SSE streaming for query results

**Quiz Focus**: Why keep Gradio if Vue3 exists? How does the frontend handle streaming responses? What state does Pinia manage?

---

## Chapter 11: Testing Strategy (测试策略)

**Learning Objectives**:
- Understand test markers: unit, integration, integration_nollm, e2e, load
- Know mocking patterns: app.dependency_overrides, AsyncMock
- Understand the factory contract testing approach

**Key Files**:
- `tests/unit/` — Unit tests (no Docker needed)
- `tests/integration/` — Docker-dependent tests
- `tests/unit/test_milvus_store_contract.py` — Contract testing pattern
- `tests/unit/test_smoke_imports.py` — Fast import check
- `tests/load/locustfile.py` — Load testing
- `conftest.py` — Shared fixtures

**Key Concepts**: Marker-based test selection, InMemoryVectorStore for contract tests, dependency_overrides for FastAPI, asyncio_mode="auto"

**Quiz Focus**: Which marker to use without Docker? How to test an endpoint without real JWT? What is contract testing?

---

## Chapter 12: Deployment & Operations (部署运维)

**Learning Objectives**:
- Understand the Docker Compose infrastructure stack
- Know the service startup order and health checks
- Understand monitoring: healthcheck.py, /readiness, traces.jsonl

**Key Files**:
- `docker-compose.yml` — Core infrastructure (PG, Milvus, Redis)
- `docker-compose.services.yml` — Model microservices
- `scripts/healthcheck.py` — Service health verification
- `docs/DEPLOYMENT_CHECKLIST.md` — Step-by-step deployment guide
- `docs/DEPLOYMENT.md` — K8s deployment architecture

**Key Concepts**: Service ports, resource limits, health checks, graceful degradation, /readiness endpoint, single-machine deployment (128GB RAM)

**Quiz Focus**: What happens if Milvus is down but PG is up? How much memory does the full stack need? What is the startup order?
