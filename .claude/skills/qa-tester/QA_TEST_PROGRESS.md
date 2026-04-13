# QA Test Progress — ChipWise Enterprise

> Generated: 2026-04-10

> Current Phase: 6

> Total: 140 test cases

> ✅ Pass: 1 | ❌ Fail: 6 | ⏭️ Skip: 133 | 🔧 Fix: 0 | ⬜ Pending: 0


<!-- STATUS LEGEND: ⬜ pending | ✅ pass | ❌ fail | ⏭️ skip | 🔧 fix (needs re-test) -->


## A. Infrastructure Health

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 12 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⏭️ | A-01 | Docker Compose services start | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | A-02 | PostgreSQL connection | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | A-03 | PostgreSQL schema validation | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | A-04 | Milvus connection | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | A-05 | Milvus collection schema | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | A-06 | Redis connectivity DB0 | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | A-07 | Redis connectivity DB1 (Celery) | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | A-08 | Kùzu graph initialization | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | A-09 | Kùzu edge tables | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | A-10 | Combined healthcheck script | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | A-11 | Port conflict detection | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | A-12 | Docker container resource usage | [SKIP] Phase 1-3 completed by user prior to this session |


## B. API Gateway

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 15 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⏭️ | B-01 | FastAPI app starts | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | B-02 | Readiness endpoint | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | B-03 | CORS headers present | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | B-04 | Request trace_id injection | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | B-05 | Unauthenticated query rejected | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | B-06 | Valid JWT query succeeds | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | B-07 | Expired JWT rejected | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | B-08 | Rate limit per-minute | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | B-09 | Rate limit hourly | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | B-10 | Prometheus metrics endpoint | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | B-11 | Invalid JSON body | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | B-12 | RBAC viewer role | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | B-13 | RBAC admin role | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | B-14 | OPTIONS preflight CORS | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | B-15 | Oversized request body | [SKIP] Phase 1-3 completed by user prior to this session |


## C. Security (JWT / RBAC / Rate Limit)

> ✅ Pass: 1 | ❌ Fail: 3 | ⏭️ Skip: 6 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⏭️ | C-01 | JWT RS256 signature verification | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | C-02 | JWT token refresh flow | [SKIP] Phase 1-3 completed by user prior to this session |
| ❌ | C-03 | SSO/OIDC login redirect | curl GET /api/v1/auth/sso/login?provider=keycloak → HTTP 404 Not Found, body={"detail":"Not Found"}; SSO auth router not registered in src/api/main.py; no /api/v1/auth/sso/* routes in OpenAPI spec |
| ❌ | C-04 | SSO callback token exchange | curl GET /api/v1/auth/sso/callback?code=testcode&state=teststate → HTTP 404 Not Found; same root cause as C-03 — SSO router not registered; Keycloak not running in dev environment |
| ❌ | C-05 | JIT user provisioning | curl GET /api/v1/auth/sso/login?provider=keycloak → HTTP 404; SSO login endpoint absent, cannot trigger JIT provisioning flow; users table auto-creation untestable |
| ✅ | C-06 | Local auth fallback | POST /api/v1/auth/login status=200, access_token=eyJhbGci...DpI, token_type=bearer, expires_in=1800; Keycloak not running, local auth succeeded independently |
| ⏭️ | C-07 | SQL injection attempt | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | C-08 | XSS in document metadata | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | C-09 | Path traversal in download | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | C-10 | Sensitive fields masked in logs | [SKIP] Phase 1-3 completed by user prior to this session |


## D. Agent Orchestrator

> ✅ Pass: 0 | ❌ Fail: 2 | ⏭️ Skip: 13 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⏭️ | D-01 | Simple query — single ReAct iteration | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | D-02 | Comparison query — multi-tool | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | D-03 | Max iterations limit (5) | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | D-04 | TokenBudget exhaustion | [SKIP] Phase 1-3 completed by user prior to this session |
| ❌ | D-05 | Tool selection: chip comparison | POST /api/v1/query status=200 but body={"answer":"Query received: Compare STM32F407 vs GD32F407 peripherals","citations":[],"trace_id":""}. Bugs: (1) query router is a stub — never calls Agent Orchestrator; (2) query endpoint has no JWT auth dependency; (3) LM Studio :1234 DOWN so Agent cannot run even if wired |
| ❌ | D-06 | Tool selection: BOM review | POST /api/v1/query status=200 body={"answer":"Query received: Review this BOM for component availability","citations":[],"trace_id":""}. Same root cause as D-05: stub query router, no Agent call, no bom_review tool selected in trace |
| ⏭️ | D-07 | Tool selection: graph query (errata) | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | D-08 | Parallel tool calls | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | D-09 | Safety guardrail: prompt injection | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | D-10 | Safety guardrail: hallucination check | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | D-11 | StructuredOutputValidator: valid output | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | D-12 | StructuredOutputValidator: retry on invalid | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | D-13 | Trace records all iterations | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | D-14 | Tool timeout handling | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | D-15 | Tool exception handling | [SKIP] Phase 1-3 completed by user prior to this session |


## E. Core Services

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 10 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⏭️ | E-01 | QueryRewriter: pronoun resolution | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | E-02 | QueryRewriter: intent classification | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | E-03 | QueryRewriter: entity extraction | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | E-04 | ConversationManager: store session | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | E-05 | ConversationManager: TTL expiry | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | E-06 | GPTCache: cache miss | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | E-07 | GPTCache: cache hit | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | E-08 | GPTCache: invalidation on ingest | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | E-09 | ResponseBuilder: markdown citations | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | E-10 | ResponseBuilder: trace finalization | [SKIP] Phase 1-3 completed by user prior to this session |


## F. Retrieval & Storage

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 15 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⏭️ | F-01 | MilvusStore: upsert dense+sparse | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | F-02 | MilvusStore: hybrid_search RRF | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | F-03 | MilvusStore: delete by document_id | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | F-04 | MilvusStore: collection statistics | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | F-05 | BGEM3Client: encode dense+sparse | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | F-06 | BGEM3Client: batch encoding | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | F-07 | BCERerankerClient: rerank | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | F-08 | BCERerankerClient: fallback on down | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | F-09 | KuzuGraphStore: Cypher query | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | F-10 | KuzuGraphStore: upsert node+edge | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | F-11 | FusionStrategy: RRF dense+sparse+graph | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | F-12 | PostgreSQL: CRUD chips table | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | F-13 | PostgreSQL: parameterized query | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | F-14 | Redis: session CRUD (DB0) | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | F-15 | Redis: Celery broker (DB1) | [SKIP] Phase 1-3 completed by user prior to this session |


## G. Ingestion Pipeline

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 15 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⏭️ | G-01 | Upload PDF via API | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | G-02 | Celery task chain completes | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | G-03 | PDF text extraction (pdfplumber) | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | G-04 | Table extraction (3-tier fallback) | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | G-05 | LLM parameter extraction | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | G-06 | Datasheet chunk boundaries | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | G-07 | Table chunker: intact tables | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | G-08 | BGE-M3 embedding generation | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | G-09 | Milvus upsert after ingestion | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | G-10 | Kùzu graph sync | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | G-11 | SHA256 deduplication | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | G-12 | Force re-ingest | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | G-13 | Task progress WebSocket | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | G-14 | Watchdog directory monitor | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | G-15 | PaddleOCR heavy worker | [SKIP] Phase 1-3 completed by user prior to this session |


## H. Model Services

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 10 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⏭️ | H-01 | BGE-M3 /encode endpoint | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | H-02 | BGE-M3 /health | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | H-03 | bce-reranker /rerank endpoint | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | H-04 | bce-reranker /health | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | H-05 | LM Studio primary model responds | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | H-06 | LM Studio router model responds | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | H-07 | LM Studio /v1/models lists loaded | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | H-08 | LM Studio concurrency limit | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | H-09 | BGE-M3 batch performance | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | H-10 | Circuit breaker on model failure | [SKIP] Phase 1-3 completed by user prior to this session |


## I. Gradio Frontend

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 10 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⏭️ | I-01 | Gradio app loads | [SKIP] curl http://localhost:7860/ → CONNECTION_FAILED; gradio package not installed in .venv; frontend cannot start |
| ⏭️ | I-02 | Chat query submission | [SKIP] Gradio not installed, port 7860 CONNECTION_FAILED; Gradio predict API unreachable |
| ⏭️ | I-03 | SSE streaming tokens | [SKIP] Gradio not installed, port 7860 CONNECTION_FAILED; SSE streaming endpoint unreachable |
| ⏭️ | I-04 | File upload triggers ingestion | [SKIP] Gradio not installed, port 7860 CONNECTION_FAILED; file upload component unreachable |
| ⏭️ | I-05 | Chip comparison UI | [SKIP] Gradio not installed, port 7860 CONNECTION_FAILED; comparison tab unreachable |
| ⏭️ | I-06 | BOM upload UI | [SKIP] Gradio not installed, port 7860 CONNECTION_FAILED; BOM upload tab unreachable |
| ⏭️ | I-07 | System status dashboard | [SKIP] Gradio not installed, port 7860 CONNECTION_FAILED; monitoring tab unreachable |
| ⏭️ | I-08 | Error state display | [SKIP] Gradio not installed, port 7860 CONNECTION_FAILED; error state UI untestable |
| ⏭️ | I-09 | Session persistence | [SKIP] Gradio not installed, port 7860 CONNECTION_FAILED; session persistence UI untestable |
| ⏭️ | I-10 | Responsive layout | [SKIP] Gradio not installed, port 7860 CONNECTION_FAILED; layout testing requires running frontend |


## J. Config & Fault Tolerance

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 12 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⏭️ | J-01 | settings.yaml loads successfully | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | J-02 | Environment variable override | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | J-03 | YAML syntax error handling | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | J-04 | Missing required field | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | J-05 | Invalid LLM endpoint | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | J-06 | Invalid embedding endpoint | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | J-07 | Milvus down: degraded search | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | J-08 | Redis down: degraded mode | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | J-09 | PostgreSQL down: degraded mode | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | J-10 | LM Studio down: circuit breaker | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | J-11 | Chunk size parameter change | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | J-12 | traces.jsonl deleted recovery | [SKIP] Phase 1-3 completed by user prior to this session |


## K. Data Lifecycle

> ✅ Pass: 0 | ❌ Fail: 1 | ⏭️ Skip: 7 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⏭️ | K-01 | Full lifecycle: upload→query→delete→query | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | K-02 | Cross-storage delete verification | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | K-03 | Multi-collection isolation | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | K-04 | Re-ingest after delete | [SKIP] Phase 1-3 completed by user prior to this session |
| ❌ | K-05 | BOM upload→review→export | Step1: POST /api/v1/documents/upload status=200, task_id=upload-sample_bom.xlsx-450673344, file_size=5193. Step2: POST /api/v1/query → stub body={"answer":"Query received: Review...","citations":[],"trace_id":""} — bom_review tool NOT invoked. Step3: not reached. VERDICT: FAIL |
| ⏭️ | K-06 | Graph sync after ingestion | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | K-07 | Cache invalidation on ingest | [SKIP] Phase 1-3 completed by user prior to this session |
| ⏭️ | K-08 | Bulk directory ingestion | [SKIP] Phase 1-3 completed by user prior to this session |


## L. RAG Quality

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 8 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⏭️ | L-01 | Hit Rate@10 ≥ 90% | [SKIP] BGE-M3 :8001 DOWN (CONNECTION_FAILED); embedding required for hit-rate evaluation over Milvus |
| ⏭️ | L-02 | NDCG@10 ≥ 0.85 | [SKIP] BGE-M3 :8001 DOWN; NDCG requires embedding + Milvus hybrid search |
| ⏭️ | L-03 | MRR ≥ 0.80 | [SKIP] BGE-M3 :8001 DOWN; MRR requires embedding + Milvus RRF ranking |
| ⏭️ | L-04 | EM ≥ 70% (parameter extraction) | [SKIP] LM Studio :1234 DOWN (CONNECTION_FAILED); EM evaluation requires LLM for answer generation |
| ⏭️ | L-05 | F1 ≥ 85% (token-level) | [SKIP] LM Studio :1234 DOWN; F1 evaluation requires LLM-generated answers |
| ⏭️ | L-06 | Faithfulness ≥ 90% | [SKIP] LM Studio :1234 DOWN; faithfulness evaluation requires LLM pipeline |
| ⏭️ | L-07 | Tool Selection Accuracy ≥ 90% | [SKIP] LM Studio :1234 DOWN; tool selection requires ReAct agent loop with LLM |
| ⏭️ | L-08 | Graph Query Hit Rate ≥ 85% | [SKIP] LM Studio :1234 DOWN; graph query hit rate requires LLM-driven Agent graph_query tool |
