# Coverage Gaps Report

**Generated**: 2026-04-14
**Baseline**: 77% overall (693 unit tests passed)
**Gate**: `--cov-fail-under=65`

## Modules Below 60% Coverage

| Module | Coverage | Missing Lines | Priority | Suggested Test Focus |
|--------|----------|--------------|----------|---------------------|
| `src/cache/cache_invalidator.py` | 0% | 47 | High | Invalidation logic; mock Redis client |
| `src/api/routers/sso.py` | 25% | 49 | Med | Login redirect + callback; mock SSO providers |
| `src/ingestion/chunking/coarse_chunker.py` | 27% | 35 | Med | Chunk boundary logic with sample text |
| `src/api/routers/health.py` | 44% | 61 | High | `/readiness` degraded modes; mock service checks |
| `src/ingestion/chunking/fine_chunker.py` | 35% | 20 | Med | Fine-grained splitting edge cases |
| `src/auth/sso/keycloak.py` | 32% | 34 | Low | OIDC flow; requires heavy mocking |
| `src/libs/vector_store/milvus_store.py` | 33% | 65 | Med | CRUD ops; mock pymilvus |
| `src/ingestion/crawler.py` | 36% | 39 | Low | Playwright-dependent; hard to unit test |
| `src/api/routers/tasks.py` | 42% | 28 | Med | WebSocket push + task status; mock Celery |
| `src/auth/sso/feishu.py` | 46% | 13 | Low | OIDC flow; mock httpx |
| `src/ingestion/pdf_extractor.py` | 50% | 67 | Med | 3-tier extraction; mock pdfplumber/camelot |
| `src/api/dependencies.py` | 51% | 51 | High | Rate limiter + auth dependency; mock Redis |
| `src/auth/sso/dingtalk.py` | 52% | 10 | Low | OIDC flow; mock httpx |
| `src/ingestion/tasks.py` | 52% | 70 | Med | Celery task chains; mock workers |
| `src/retrieval/sql_search.py` | 57% | 10 | Med | SQL query execution paths |
| `src/api/routers/query.py` | 58% | 45 | High | Orchestrator singleton + SSE stream |

## Top 5 Recommended for Phase 8 Improvement

1. **`cache_invalidator.py`** (0% → 70%+) — Pure logic, easy to mock Redis
2. **`health.py`** (44% → 70%+) — Critical path, test degraded/healthy/unhealthy
3. **`dependencies.py`** (51% → 70%+) — Auth + rate limit dependency injection
4. **`tasks.py` router** (42% → 70%+) — Task status endpoint + WebSocket
5. **`query.py` router** (58% → 70%+) — Orchestrator lazy init + 503 handling

## Overall Stats

- **Libs layer**: ~95% avg ✅ (target ≥90%)
- **Core layer**: ~85% avg ✅ (target ≥80%)
- **API layer**: ~60% avg ⚠️ (target ≥70%, needs Phase 8 work)
- **Ingestion**: ~65% avg (acceptable, Celery/OCR hard to unit test)
