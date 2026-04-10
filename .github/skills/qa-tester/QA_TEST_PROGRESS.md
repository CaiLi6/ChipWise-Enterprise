# QA Test Progress — ChipWise Enterprise

> Generated: 2026-04-10

> Current Phase: 1

> Total: 140 test cases

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 0 | 🔧 Fix: 0 | ⬜ Pending: 140


<!-- STATUS LEGEND: ⬜ pending | ✅ pass | ❌ fail | ⏭️ skip | 🔧 fix (needs re-test) -->


## A. Infrastructure Health

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 0 | 🔧 Fix: 0 | ⬜ Pending: 12

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⬜ | A-01 | Docker Compose services start | |
| ⬜ | A-02 | PostgreSQL connection | |
| ⬜ | A-03 | PostgreSQL schema validation | |
| ⬜ | A-04 | Milvus connection | |
| ⬜ | A-05 | Milvus collection schema | |
| ⬜ | A-06 | Redis connectivity DB0 | |
| ⬜ | A-07 | Redis connectivity DB1 (Celery) | |
| ⬜ | A-08 | Kùzu graph initialization | |
| ⬜ | A-09 | Kùzu edge tables | |
| ⬜ | A-10 | Combined healthcheck script | |
| ⬜ | A-11 | Port conflict detection | |
| ⬜ | A-12 | Docker container resource usage | |


## B. API Gateway

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 0 | 🔧 Fix: 0 | ⬜ Pending: 15

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⬜ | B-01 | FastAPI app starts | |
| ⬜ | B-02 | Readiness endpoint | |
| ⬜ | B-03 | CORS headers present | |
| ⬜ | B-04 | Request trace_id injection | |
| ⬜ | B-05 | Unauthenticated query rejected | |
| ⬜ | B-06 | Valid JWT query succeeds | |
| ⬜ | B-07 | Expired JWT rejected | |
| ⬜ | B-08 | Rate limit per-minute | |
| ⬜ | B-09 | Rate limit hourly | |
| ⬜ | B-10 | Prometheus metrics endpoint | |
| ⬜ | B-11 | Invalid JSON body | |
| ⬜ | B-12 | RBAC viewer role | |
| ⬜ | B-13 | RBAC admin role | |
| ⬜ | B-14 | OPTIONS preflight CORS | |
| ⬜ | B-15 | Oversized request body | |


## C. Security (JWT / RBAC / Rate Limit)

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 0 | 🔧 Fix: 0 | ⬜ Pending: 10

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⬜ | C-01 | JWT RS256 signature verification | |
| ⬜ | C-02 | JWT token refresh flow | |
| ⬜ | C-03 | SSO/OIDC login redirect | |
| ⬜ | C-04 | SSO callback token exchange | |
| ⬜ | C-05 | JIT user provisioning | |
| ⬜ | C-06 | Local auth fallback | |
| ⬜ | C-07 | SQL injection attempt | |
| ⬜ | C-08 | XSS in document metadata | |
| ⬜ | C-09 | Path traversal in download | |
| ⬜ | C-10 | Sensitive fields masked in logs | |


## D. Agent Orchestrator

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 0 | 🔧 Fix: 0 | ⬜ Pending: 15

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⬜ | D-01 | Simple query — single ReAct iteration | |
| ⬜ | D-02 | Comparison query — multi-tool | |
| ⬜ | D-03 | Max iterations limit (5) | |
| ⬜ | D-04 | TokenBudget exhaustion | |
| ⬜ | D-05 | Tool selection: chip comparison | |
| ⬜ | D-06 | Tool selection: BOM review | |
| ⬜ | D-07 | Tool selection: graph query (errata) | |
| ⬜ | D-08 | Parallel tool calls | |
| ⬜ | D-09 | Safety guardrail: prompt injection | |
| ⬜ | D-10 | Safety guardrail: hallucination check | |
| ⬜ | D-11 | StructuredOutputValidator: valid output | |
| ⬜ | D-12 | StructuredOutputValidator: retry on invalid | |
| ⬜ | D-13 | Trace records all iterations | |
| ⬜ | D-14 | Tool timeout handling | |
| ⬜ | D-15 | Tool exception handling | |


## E. Core Services

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 0 | 🔧 Fix: 0 | ⬜ Pending: 10

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⬜ | E-01 | QueryRewriter: pronoun resolution | |
| ⬜ | E-02 | QueryRewriter: intent classification | |
| ⬜ | E-03 | QueryRewriter: entity extraction | |
| ⬜ | E-04 | ConversationManager: store session | |
| ⬜ | E-05 | ConversationManager: TTL expiry | |
| ⬜ | E-06 | GPTCache: cache miss | |
| ⬜ | E-07 | GPTCache: cache hit | |
| ⬜ | E-08 | GPTCache: invalidation on ingest | |
| ⬜ | E-09 | ResponseBuilder: markdown citations | |
| ⬜ | E-10 | ResponseBuilder: trace finalization | |


## F. Retrieval & Storage

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 0 | 🔧 Fix: 0 | ⬜ Pending: 15

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⬜ | F-01 | MilvusStore: upsert dense+sparse | |
| ⬜ | F-02 | MilvusStore: hybrid_search RRF | |
| ⬜ | F-03 | MilvusStore: delete by document_id | |
| ⬜ | F-04 | MilvusStore: collection statistics | |
| ⬜ | F-05 | BGEM3Client: encode dense+sparse | |
| ⬜ | F-06 | BGEM3Client: batch encoding | |
| ⬜ | F-07 | BCERerankerClient: rerank | |
| ⬜ | F-08 | BCERerankerClient: fallback on down | |
| ⬜ | F-09 | KuzuGraphStore: Cypher query | |
| ⬜ | F-10 | KuzuGraphStore: upsert node+edge | |
| ⬜ | F-11 | FusionStrategy: RRF dense+sparse+graph | |
| ⬜ | F-12 | PostgreSQL: CRUD chips table | |
| ⬜ | F-13 | PostgreSQL: parameterized query | |
| ⬜ | F-14 | Redis: session CRUD (DB0) | |
| ⬜ | F-15 | Redis: Celery broker (DB1) | |


## G. Ingestion Pipeline

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 0 | 🔧 Fix: 0 | ⬜ Pending: 15

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⬜ | G-01 | Upload PDF via API | |
| ⬜ | G-02 | Celery task chain completes | |
| ⬜ | G-03 | PDF text extraction (pdfplumber) | |
| ⬜ | G-04 | Table extraction (3-tier fallback) | |
| ⬜ | G-05 | LLM parameter extraction | |
| ⬜ | G-06 | Datasheet chunk boundaries | |
| ⬜ | G-07 | Table chunker: intact tables | |
| ⬜ | G-08 | BGE-M3 embedding generation | |
| ⬜ | G-09 | Milvus upsert after ingestion | |
| ⬜ | G-10 | Kùzu graph sync | |
| ⬜ | G-11 | SHA256 deduplication | |
| ⬜ | G-12 | Force re-ingest | |
| ⬜ | G-13 | Task progress WebSocket | |
| ⬜ | G-14 | Watchdog directory monitor | |
| ⬜ | G-15 | PaddleOCR heavy worker | |


## H. Model Services

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 0 | 🔧 Fix: 0 | ⬜ Pending: 10

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⬜ | H-01 | BGE-M3 /encode endpoint | |
| ⬜ | H-02 | BGE-M3 /health | |
| ⬜ | H-03 | bce-reranker /rerank endpoint | |
| ⬜ | H-04 | bce-reranker /health | |
| ⬜ | H-05 | LM Studio primary model responds | |
| ⬜ | H-06 | LM Studio router model responds | |
| ⬜ | H-07 | LM Studio /v1/models lists loaded | |
| ⬜ | H-08 | LM Studio concurrency limit | |
| ⬜ | H-09 | BGE-M3 batch performance | |
| ⬜ | H-10 | Circuit breaker on model failure | |


## I. Gradio Frontend

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 0 | 🔧 Fix: 0 | ⬜ Pending: 10

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⬜ | I-01 | Gradio app loads | |
| ⬜ | I-02 | Chat query submission | |
| ⬜ | I-03 | SSE streaming tokens | |
| ⬜ | I-04 | File upload triggers ingestion | |
| ⬜ | I-05 | Chip comparison UI | |
| ⬜ | I-06 | BOM upload UI | |
| ⬜ | I-07 | System status dashboard | |
| ⬜ | I-08 | Error state display | |
| ⬜ | I-09 | Session persistence | |
| ⬜ | I-10 | Responsive layout | |


## J. Config & Fault Tolerance

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 0 | 🔧 Fix: 0 | ⬜ Pending: 12

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⬜ | J-01 | settings.yaml loads successfully | |
| ⬜ | J-02 | Environment variable override | |
| ⬜ | J-03 | YAML syntax error handling | |
| ⬜ | J-04 | Missing required field | |
| ⬜ | J-05 | Invalid LLM endpoint | |
| ⬜ | J-06 | Invalid embedding endpoint | |
| ⬜ | J-07 | Milvus down: degraded search | |
| ⬜ | J-08 | Redis down: degraded mode | |
| ⬜ | J-09 | PostgreSQL down: degraded mode | |
| ⬜ | J-10 | LM Studio down: circuit breaker | |
| ⬜ | J-11 | Chunk size parameter change | |
| ⬜ | J-12 | traces.jsonl deleted recovery | |


## K. Data Lifecycle

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 0 | 🔧 Fix: 0 | ⬜ Pending: 8

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⬜ | K-01 | Full lifecycle: upload→query→delete→query | |
| ⬜ | K-02 | Cross-storage delete verification | |
| ⬜ | K-03 | Multi-collection isolation | |
| ⬜ | K-04 | Re-ingest after delete | |
| ⬜ | K-05 | BOM upload→review→export | |
| ⬜ | K-06 | Graph sync after ingestion | |
| ⬜ | K-07 | Cache invalidation on ingest | |
| ⬜ | K-08 | Bulk directory ingestion | |


## L. RAG Quality

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 0 | 🔧 Fix: 0 | ⬜ Pending: 8

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⬜ | L-01 | Hit Rate@10 ≥ 90% | |
| ⬜ | L-02 | NDCG@10 ≥ 0.85 | |
| ⬜ | L-03 | MRR ≥ 0.80 | |
| ⬜ | L-04 | EM ≥ 70% (parameter extraction) | |
| ⬜ | L-05 | F1 ≥ 85% (token-level) | |
| ⬜ | L-06 | Faithfulness ≥ 90% | |
| ⬜ | L-07 | Tool Selection Accuracy ≥ 90% | |
| ⬜ | L-08 | Graph Query Hit Rate ≥ 85% | |
