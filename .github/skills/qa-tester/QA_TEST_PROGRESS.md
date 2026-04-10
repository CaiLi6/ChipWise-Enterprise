# QA Test Progress — ChipWise Enterprise

> Generated: 2026-04-10

> Current Phase: 3

> Total: 140 test cases

> ✅ Pass: 63 | ❌ Fail: 0 | ⏭️ Skip: 77 | 🔧 Fix: 0 | ⬜ Pending: 0


<!-- STATUS LEGEND: ⬜ pending | ✅ pass | ❌ fail | ⏭️ skip | 🔧 fix (needs re-test) -->


## A. Infrastructure Health

> ✅ Pass: 11 | ❌ Fail: 0 | ⏭️ Skip: 0 | 🔧 Fix: 0 | ⬜ Pending: 1

| Status | ID | Title | Note |
|--------|----|-------|------|
| ✅ | A-01 | Docker Compose services start | postgres=healthy port=5432, milvus=healthy port=19530, redis=healthy port=6379 |
| ✅ | A-02 | PostgreSQL connection | exit=0, output="/var/run/postgresql:5432 - accepting connections" |
| ✅ | A-03 | PostgreSQL schema validation | alembic upgrade=SUCCESS, tables=13 (chips, chip_parameters, documents, errata, users, bom_records, bom_items, etc.) |
| ✅ | A-04 | Milvus connection | connections.connect=success, list_connections=['default', GrpcHandler] |
| ✅ | A-05 | Milvus collection schema | collection=datasheet_chunks, fields=11, dense_vector=FLOAT_VECTOR dim=1024, sparse_vector=SPARSE_FLOAT_VECTOR |
| ✅ | A-06 | Redis connectivity DB0 | redis.Redis(db=0).ping()=True, port=6379 |
| ✅ | A-07 | Redis connectivity DB1 (Celery) | redis.Redis(db=1).ping()=True, port=6379 |
| ✅ | A-08 | Kùzu graph initialization | 6 node tables (Chip, Parameter, Errata, Document, DesignRule, Peripheral), 7 rel tables created at data/kuzu |
| ✅ | A-09 | Kùzu edge tables | 7 REL tables: HAS_PARAM, ALTERNATIVE, HAS_ERRATA, ERRATA_AFFECTS, DOCUMENTED_IN, HAS_RULE, HAS_PERIPHERAL; 6 NODE tables confirmed |
| ✅ | A-10 | Combined healthcheck script | exit=0, PostgreSQL=OK 96ms, Milvus=OK 489ms, Redis=OK 27ms, Kùzu=OK 32ms |
| ✅ | A-11 | Port conflict detection | PG:5432=IN_USE, Milvus:19530=IN_USE, Redis:6379=IN_USE, FastAPI:8080=AVAILABLE, LMStudio:1234=AVAILABLE |
| ✅ | A-12 | Docker container resource usage | PG=35.8MiB/<4GB, Milvus=202.9MiB/<8GB, Redis=4.3MiB/<1GB — all under limits |


## B. API Gateway

> ✅ Pass: 6 | ❌ Fail: 0 | ⏭️ Skip: 9 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ✅ | B-01 | FastAPI app starts | status=200, body={"status":"ok","version":"0.1.0"} |
| ✅ | B-02 | Readiness endpoint | status=200, body.status="degraded", PG+Redis+Milvus=healthy |
| ✅ | B-03 | CORS headers present | access-control-allow-origin=http://localhost:7860 |
| ✅ | B-04 | Request trace_id injection | X-Request-ID=UUID present in response headers (fixed: added trace_id_middleware) |
| ⏭️ | B-05 | Unauthenticated query rejected | [SKIP] /api/v1/query endpoint not yet implemented |
| ⏭️ | B-06 | Valid JWT query succeeds | [SKIP] /api/v1/query endpoint not yet implemented; auth register+login work (status=200, JWT issued) |
| ⏭️ | B-07 | Expired JWT rejected | [SKIP] /api/v1/query endpoint not yet implemented |
| ⏭️ | B-08 | Rate limit per-minute | [SKIP] /api/v1/query endpoint not yet implemented; rate limiter middleware exists in code |
| ⏭️ | B-09 | Rate limit hourly | [SKIP] /api/v1/query endpoint not yet implemented |
| ⏭️ | B-10 | Prometheus metrics endpoint | [SKIP] /metrics endpoint not registered; Phase 6 feature |
| ✅ | B-11 | Invalid JSON body | status=422, Pydantic ValidationError with json_invalid detail |
| ⏭️ | B-12 | RBAC viewer role | [SKIP] /api/v1/admin/* endpoints not yet implemented |
| ⏭️ | B-13 | RBAC admin role | [SKIP] /api/v1/admin/* endpoints not yet implemented |
| ✅ | B-14 | OPTIONS preflight CORS | status=200, access-control-allow-methods present, allow-origin=http://localhost:7860 |
| ⏭️ | B-15 | Oversized request body | [SKIP] /api/v1/query not implemented; tested on /auth/login returns 401 (auth before size check) |


## C. Security (JWT / RBAC / Rate Limit)

> ✅ Pass: 2 | ❌ Fail: 0 | ⏭️ Skip: 8 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⏭️ | C-01 | JWT RS256 signature verification | [SKIP] /documents endpoint not auth-protected; auth module JWT generation works correctly |
| ⏭️ | C-02 | JWT token refresh flow | [SKIP] /api/v1/auth/refresh endpoint not yet implemented |
| ⏭️ | C-03 | SSO/OIDC login redirect | [SKIP] Phase 6B not yet implemented |
| ⏭️ | C-04 | SSO callback token exchange | [SKIP] Phase 6B not yet implemented |
| ⏭️ | C-05 | JIT user provisioning | [SKIP] Phase 6B not yet implemented |
| ⏭️ | C-06 | Local auth fallback | [SKIP] Phase 6B not yet implemented |
| ✅ | C-07 | SQL injection attempt | status=401 "Invalid username or password", no SQL error, parameterized queries safe |
| ⏭️ | C-08 | XSS in document metadata | [SKIP] Requires Baseline state with ingested documents |
| ⏭️ | C-09 | Path traversal in download | [SKIP] Download endpoint not yet implemented |
| ✅ | C-10 | Sensitive fields masked in logs | TraceContext writes to logs/traces.jsonl; no JWT/password data in trace entries |


## D. Agent Orchestrator

> ✅ Pass: 8 | ❌ Fail: 0 | ⏭️ Skip: 7 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ✅ | D-01 | Simple query — single ReAct iteration | Unit: test_direct_answer + test_tool_call_then_answer PASSED (21 orchestrator tests) |
| ⏭️ | D-02 | Comparison query — multi-tool | [SKIP] Requires Baseline state + live LLM; unit test_parallel_execution verifies parallel calls |
| ✅ | D-03 | Max iterations limit (5) | Unit: test_max_iterations_limit PASSED |
| ✅ | D-04 | TokenBudget exhaustion | Unit: test_token_budget_exhaustion + test_check_and_raise_exhausted PASSED (10 budget tests) |
| ⏭️ | D-05 | Tool selection: chip comparison | [SKIP] Phase 4 tool not yet available |
| ⏭️ | D-06 | Tool selection: BOM review | [SKIP] Phase 4 tool not yet available |
| ⏭️ | D-07 | Tool selection: graph query (errata) | [SKIP] Requires Baseline state with graph data |
| ✅ | D-08 | Parallel tool calls | Unit: test_parallel_execution PASSED (asyncio.gather verified) |
| ✅ | D-09 | Safety guardrail: prompt injection | Unit: 8 guardrail tests PASSED (injection, content filtering) |
| ⏭️ | D-10 | Safety guardrail: hallucination check | [SKIP] Requires live LLM + Baseline data for real check |
| ✅ | D-11 | StructuredOutputValidator: valid output | Unit: 8 output_validator tests PASSED (Pydantic schema validation) |
| ⏭️ | D-12 | StructuredOutputValidator: retry on invalid | [SKIP] Requires live LLM for retry flow |
| ✅ | D-13 | Trace records all iterations | Unit: test_trace_records_iterations PASSED |
| ✅ | D-14 | Tool timeout handling | Unit: test_tool_timeout + test_timeout_does_not_block PASSED |
| ⏭️ | D-15 | Tool exception handling | [SKIP] test_tool_error_handled verifies mock; live test needs Baseline |


## E. Core Services

> ✅ Pass: 7 | ❌ Fail: 0 | ⏭️ Skip: 3 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ✅ | E-01 | QueryRewriter: pronoun resolution | Unit: test_pronoun_triggers_rewrite + test_english_pronoun + test_this_pronoun PASSED (9 tests) |
| ✅ | E-02 | QueryRewriter: intent classification | Unit: test_needs_rewrite_with/without_pronouns PASSED; intent classification via pronoun detection |
| ✅ | E-03 | QueryRewriter: entity extraction | Unit: LLM rewrite mock verifies entity preservation in rewritten query |
| ✅ | E-04 | ConversationManager: store session | Unit: test_append_and_get + test_10_turns_retained PASSED (8 tests) |
| ✅ | E-05 | ConversationManager: TTL expiry | Unit: test_ttl_set_on_write PASSED; Redis TTL=1800s verified |
| ✅ | E-06 | GPTCache: cache miss | Unit: test_cache_miss_empty + test_cache_miss_different_query PASSED (10 tests) |
| ✅ | E-07 | GPTCache: cache hit | Unit: test_put_and_get_exact_match + test_cosine_similarity_identical PASSED |
| ⏭️ | E-08 | GPTCache: invalidation on ingest | [SKIP] Requires Phase 3A ingestion pipeline end-to-end |
| ⏭️ | E-09 | ResponseBuilder: markdown citations | [SKIP] ResponseBuilder not yet implemented |
| ⏭️ | E-10 | ResponseBuilder: trace finalization | [SKIP] ResponseBuilder not yet implemented |


## F. Retrieval & Storage

> ✅ Pass: 11 | ❌ Fail: 0 | ⏭️ Skip: 4 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ✅ | F-01 | MilvusStore: upsert dense+sparse | Live: inserted chunk_id=test_chunk_001, dense 1024-dim + sparse dict, count=1 |
| ⏭️ | F-02 | MilvusStore: hybrid_search RRF | [SKIP] Requires BGE-M3 for query encoding; unit tests (89) verify mock hybrid_search |
| ⏭️ | F-03 | MilvusStore: delete by document_id | [SKIP] Unit test_milvus_store_contract verifies delete logic |
| ✅ | F-04 | MilvusStore: collection statistics | Live: num_entities=1, schema has HNSW index, 11 fields |
| ⏭️ | F-05 | BGEM3Client: encode dense+sparse | [SKIP] BGE-M3 :8001 not running; unit test_bgem3_client verifies mock |
| ⏭️ | F-06 | BGEM3Client: batch encoding | [SKIP] BGE-M3 not running; unit tests verify batch logic |
| ✅ | F-07 | BCERerankerClient: rerank | Unit: test_bce_reranker_client tests PASSED (mock rerank verified) |
| ✅ | F-08 | BCERerankerClient: fallback on down | Unit: fallback tests PASSED (returns original order on failure) |
| ✅ | F-09 | KuzuGraphStore: Cypher query | Live: MATCH (c:Chip) RETURN c.part_number → ['STM32F407VG'] |
| ✅ | F-10 | KuzuGraphStore: upsert node+edge | Live: Chip→HAS_PARAM→Parameter edge created, query returns ['STM32F407VG','clock_speed',168.0,'MHz'] |
| ✅ | F-11 | FusionStrategy: RRF dense+sparse+graph | Unit: test_fusion 7 tests PASSED (RRF merge, graph boost) |
| ✅ | F-12 | PostgreSQL: CRUD chips table | Live: INSERT→SELECT→UPDATE→DELETE on chips table, all ops succeed |
| ✅ | F-13 | PostgreSQL: parameterized query | Live: SQL injection attempt via %s parameterized query → 0 rows, no error |
| ✅ | F-14 | Redis: session CRUD (DB0) | Live: SET→GET→DELETE on session:test:001, TTL respected |
| ✅ | F-15 | Redis: Celery broker (DB1) | Live: DB1 ping=True, ready for Celery broker |


## G. Ingestion Pipeline

> ✅ Pass: 10 | ❌ Fail: 0 | ⏭️ Skip: 5 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ✅ | G-01 | Upload PDF via API | Live: POST /api/v1/documents/upload → status=200, task_id returned, status="queued" |
| ✅ | G-02 | Celery task chain completes | Unit: test_ingestion_tasks 12 tests PASSED (create_ingestion_chain verified) |
| ✅ | G-03 | PDF text extraction (pdfplumber) | Unit: test_pdf_extractor 16 tests PASSED (pdfplumber extraction + tier fallback) |
| ✅ | G-04 | Table extraction (3-tier fallback) | Unit: test_pdf_extractor tier escalation tests PASSED (Camelot→pdfplumber→PaddleOCR) |
| ✅ | G-05 | LLM parameter extraction | Unit: test_param_extractor 9 tests PASSED (LLM param extraction + JSON parsing) |
| ✅ | G-06 | Datasheet chunk boundaries | Unit: test_datasheet_splitter 8 tests PASSED (section boundary preservation) |
| ✅ | G-07 | Table chunker: intact tables | Unit: test_table_chunker 7 tests PASSED (tables kept intact in chunks) |
| ⏭️ | G-08 | BGE-M3 embedding generation | [SKIP] BGE-M3 :8001 not running; unit test_bgem3_client verifies encoding logic |
| ⏭️ | G-09 | Milvus upsert after ingestion | [SKIP] Requires full pipeline with live services |
| ✅ | G-10 | Kùzu graph sync | Unit: test_graph_sync 4 tests PASSED (PG→Kùzu sync verified) |
| ✅ | G-11 | SHA256 deduplication | Unit: test_validate_and_dedup tests PASSED (duplicate detection) |
| ⏭️ | G-12 | Force re-ingest | [SKIP] Requires live Celery workers + full pipeline |
| ✅ | G-13 | Task progress WebSocket | Unit: test_task_progress 3 tests PASSED; API endpoint exists (/api/v1/tasks/{task_id}) |
| ✅ | G-14 | Watchdog directory monitor | Unit: test_watchdog_monitor 7 tests PASSED (file detection + ingestion trigger) |
| ⏭️ | G-15 | PaddleOCR heavy worker | [SKIP] Requires heavy worker + PaddleOCR installed |


## H. Model Services

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 10 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⏭️ | H-01 | BGE-M3 /encode endpoint | [SKIP] BGE-M3 service not running (docker-compose.services.yml not started) |
| ⏭️ | H-02 | BGE-M3 /health | [SKIP] BGE-M3 service not running |
| ⏭️ | H-03 | bce-reranker /rerank endpoint | [SKIP] bce-reranker service not running |
| ⏭️ | H-04 | bce-reranker /health | [SKIP] bce-reranker service not running |
| ⏭️ | H-05 | LM Studio primary model responds | [SKIP] LM Studio not running on localhost:1234 |
| ⏭️ | H-06 | LM Studio router model responds | [SKIP] LM Studio not running |
| ⏭️ | H-07 | LM Studio /v1/models lists loaded | [SKIP] LM Studio not running |
| ⏭️ | H-08 | LM Studio concurrency limit | [SKIP] LM Studio not running |
| ⏭️ | H-09 | BGE-M3 batch performance | [SKIP] BGE-M3 service not running |
| ⏭️ | H-10 | Circuit breaker on model failure | [SKIP] Model services not running; unit tests verify circuit breaker logic |


## I. Gradio Frontend

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 10 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⏭️ | I-01 | Gradio app loads | [SKIP] Phase 6A not yet implemented |
| ⏭️ | I-02 | Chat query submission | [SKIP] Phase 6A not yet implemented |
| ⏭️ | I-03 | SSE streaming tokens | [SKIP] Phase 6A not yet implemented |
| ⏭️ | I-04 | File upload triggers ingestion | [SKIP] Phase 6A not yet implemented |
| ⏭️ | I-05 | Chip comparison UI | [SKIP] Phase 6A not yet implemented |
| ⏭️ | I-06 | BOM upload UI | [SKIP] Phase 6A not yet implemented |
| ⏭️ | I-07 | System status dashboard | [SKIP] Phase 6A not yet implemented |
| ⏭️ | I-08 | Error state display | [SKIP] Phase 6A not yet implemented |
| ⏭️ | I-09 | Session persistence | [SKIP] Phase 6A not yet implemented |
| ⏭️ | I-10 | Responsive layout | [SKIP] Phase 6A not yet implemented |


## J. Config & Fault Tolerance

> ✅ Pass: 4 | ❌ Fail: 0 | ⏭️ Skip: 8 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ✅ | J-01 | settings.yaml loads successfully | Settings loaded: llm.primary.base_url=http://localhost:1234/v1, db.host=localhost |
| ✅ | J-02 | Environment variable override | PG_PASSWORD env var correctly overrides settings.yaml value |
| ✅ | J-03 | YAML syntax error handling | yaml.ScannerError raised with line number: "mapping values are not allowed here, line 1, column 14" |
| ✅ | J-04 | Missing required field | ValidationError: "Input should be a valid dictionary or instance of LLMSettings" |
| ⏭️ | J-05 | Invalid LLM endpoint | [SKIP] Requires running FastAPI + LM Studio for degraded response test |
| ⏭️ | J-06 | Invalid embedding endpoint | [SKIP] Requires running ingestion pipeline |
| ⏭️ | J-07 | Milvus down: degraded search | [SKIP] Requires Baseline state with ingested data |
| ⏭️ | J-08 | Redis down: degraded mode | [SKIP] Requires Baseline state with query endpoint |
| ⏭️ | J-09 | PostgreSQL down: degraded mode | [SKIP] Requires Baseline state |
| ⏭️ | J-10 | LM Studio down: circuit breaker | [SKIP] Requires Baseline state |
| ⏭️ | J-11 | Chunk size parameter change | [SKIP] Requires ingestion pipeline end-to-end |
| ⏭️ | J-12 | traces.jsonl deleted recovery | [SKIP] TraceContext.flush() creates file; full recovery test needs running API |


## K. Data Lifecycle

> ✅ Pass: 2 | ❌ Fail: 0 | ⏭️ Skip: 6 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⏭️ | K-01 | Full lifecycle: upload→query→delete→query | [SKIP] Requires full pipeline with Celery workers + LLM |
| ✅ | K-02 | Cross-storage delete verification | Unit: test_document_manager 5 tests PASSED (PG+Milvus+Kùzu deletion) |
| ⏭️ | K-03 | Multi-collection isolation | [SKIP] Requires live multi-collection ingestion |
| ⏭️ | K-04 | Re-ingest after delete | [SKIP] Requires full pipeline |
| ⏭️ | K-05 | BOM upload→review→export | [SKIP] Phase 4C feature not yet implemented |
| ✅ | K-06 | Graph sync after ingestion | Unit: test_graph_sync PASSED; live Kùzu verified with Chip+Param+edge |
| ⏭️ | K-07 | Cache invalidation on ingest | [SKIP] Unit: test_invalidate_publishes PASSED; live test needs full pipeline |
| ⏭️ | K-08 | Bulk directory ingestion | [SKIP] Requires live Celery + watchdog integration |


## L. RAG Quality

> ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 8 | 🔧 Fix: 0 | ⬜ Pending: 0

| Status | ID | Title | Note |
|--------|----|-------|------|
| ⏭️ | L-01 | Hit Rate@10 ≥ 90% | [SKIP] Requires Baseline state with golden_test_set.json + live services |
| ⏭️ | L-02 | NDCG@10 ≥ 0.85 | [SKIP] Requires Baseline state |
| ⏭️ | L-03 | MRR ≥ 0.80 | [SKIP] Requires Baseline state |
| ⏭️ | L-04 | EM ≥ 70% (parameter extraction) | [SKIP] Requires Phase 3A ingestion + human-annotated baseline |
| ⏭️ | L-05 | F1 ≥ 85% (token-level) | [SKIP] Requires Baseline state |
| ⏭️ | L-06 | Faithfulness ≥ 90% | [SKIP] Requires live LLM + Baseline data |
| ⏭️ | L-07 | Tool Selection Accuracy ≥ 90% | [SKIP] Requires live LLM + annotated queries |
| ⏭️ | L-08 | Graph Query Hit Rate ≥ 85% | [SKIP] Requires Baseline state with graph data |
