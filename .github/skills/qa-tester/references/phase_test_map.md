# Phase → Testable Sections Map

Maps ChipWise Enterprise development phases to which QA test sections become executable.

| Phase | Weeks | Completed Tasks | Newly Testable Sections | Cumulative |
|-------|-------|-----------------|------------------------|------------|
| **1** | 1-2 | 1A1-1E3 (18 tasks) | **A** (Infrastructure), **B** (API Gateway), **C** (Security: JWT + rate limit, no SSO), **H** (Model Services), **J** (Config: settings load + validation) | A, B, C*, H, J* |
| **2** | 3-4 | 2A1-2D3 (19 tasks) | **D** (Agent Orchestrator), **E** (Core Services), **F** (Retrieval & Storage), **L** (RAG Quality: partial with basic golden set) | A-F, H, J*, L* |
| **3** | 5-7 | 3A1-3C4 (13 tasks) | **G** (Ingestion Pipeline), **K** (Data Lifecycle) | A-H, J*, K, L* |
| **4** | 8-10 | 4A1-4C3 (8 tasks) | **D** extended (chip_compare, chip_select, bom_review tools), **K-05** (BOM lifecycle) | A-H, J*, K, L* |
| **5** | 11-13 | 5A1-5D2 (9 tasks) | **D** extended (test_case_gen, design_rule_check, knowledge_search, report_export), **L** (full metrics with real data) | A-H, J*, K, L |
| **6** | 14-16 | 6A1-6D3 (11 tasks) | **I** (Gradio Frontend), **C** extended (SSO/OIDC), **J** (full config + fault tolerance) | A-L (all) |
| **7** | 17-18 | 7A1-7C1 (10 tasks) | **M** (Chunking Strategies & Evaluation), **J-11** extended (strategy switching), **L** extended (chunking eval metrics) | A-M (all) |

`*` = partial coverage; some tests in that section require later phases.

## Phase-Gating Rules

1. Before testing, check `Current Phase: N` in QA_TEST_PROGRESS.md header
2. Each test case has a `Phase` column — skip if test Phase > current Phase
3. Mark skipped tests as `⏭️` with note `[SKIP] Phase N not yet implemented`
4. When phase advances, re-scan all `⏭️` tests and attempt newly-in-scope ones

## Key Dependencies by Section

| Section | Required Infrastructure | Required Source Code |
|---------|----------------------|---------------------|
| A | Docker Compose running | `scripts/healthcheck.py`, `docker-compose.yml` |
| B | FastAPI server running | `src/api/main.py`, `src/api/routes/` |
| C | FastAPI + Redis | `src/api/middleware/`, `src/core/auth.py` |
| D | FastAPI + LM Studio | `src/agent/orchestrator.py`, `src/agent/tools/` |
| E | Redis + LM Studio | `src/core/query_rewriter.py`, `src/core/conversation.py` |
| F | Milvus + Kùzu + Redis | `src/libs/vector_store/`, `src/libs/graph_store/` |
| G | Full infra + Celery | `src/ingestion/tasks.py`, `src/pipelines/` |
| H | BGE-M3 + bce-reranker + LM Studio | `src/libs/embedding/`, `src/libs/reranker/`, `src/libs/llm/` |
| I | FastAPI + Gradio | `src/frontend/app.py` |
| J | Settings file | `src/core/settings.py`, `config/settings.yaml` |
| K | Full infra + Celery | Same as G + F |
| L | Full infra + golden test set | `tests/fixtures/golden_test_set.json`, evaluation scripts |
| M | Python venv (no live services needed) | `src/ingestion/chunking/`, `evaluation/chunking/`, `tests/fixtures/golden_retrieval_qrels.jsonl` |
