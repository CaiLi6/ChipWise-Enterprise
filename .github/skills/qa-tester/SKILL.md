---
name: qa-tester
description: "Fully autonomous QA testing agent for ChipWise Enterprise. Reads test cases from QA_TEST_PLAN.md, executes ALL test types automatically — FastAPI endpoints via httpx/curl, Docker infrastructure health checks, Agent orchestration flows, Celery ingestion pipelines, Milvus/Kùzu/Redis storage verification, Gradio frontend, and RAG quality evaluation. Diagnoses failures, applies fixes with up to 3 retry rounds, records results in QA_TEST_PROGRESS.md. Use when user says 'run QA', 'QA test', 'QA 测试', '执行测试', '跑测试', 'test and fix', 'chipwise test', or wants to execute QA test plan."
---

# QA Tester — ChipWise Enterprise

All test types (API / Docker / Agent / Ingestion / Storage / Frontend) are **fully automated** — zero human intervention.

Optional modifiers: append section letter (`run QA B`) or test ID (`run QA B-01`).

---

> ## ⛔ IRON RULES
>
> ### Rule 1: STRICTLY SERIAL
> Pick ONE test → Run ONE command → Wait for output → Record ONE row in `.github/skills/qa-tester/QA_TEST_PROGRESS.md` → THEN pick next.
> NEVER run two tests in one command. NEVER record two rows in one file edit. NEVER use parallel tool calls. NEVER plan the next test before recording the current one.
>
> ### Rule 2: PASS = TERMINAL OUTPUT EVIDENCE
> ✅ means you ran a command **in THIS session** and the Note contains **concrete values** copied from that output.
> No terminal output for THIS test → mark ⬜. NEVER ✅.
>
> ### Rule 3: ZERO CROSS-REFERENCING
> NEVER write "Verified via X-YZ", "Already verified in C-02", "Same as…", "Similar to…".
> Even if B-05 tests the same endpoint as C-02, run B-05 independently and paste its own output.
>
> ### Rule 4: ZERO INFERENCE
> **BANNED Note patterns** (caught by validator):
> "Code uses…" / "Dataclass validates…" / "auto-creates…" → Reading code ≠ testing.
> "Should work…" / "Would raise…" / "Expected behavior…" → Speculation ≠ testing.
> "Parameter accepted" / "Config controls behavior" → Vague. No output = no pass.
> If you didn't run a command and see output for THIS test, mark ⬜.
>
> ### Rule 5: ADVERSARIAL MINDSET
> Find bugs, not confirmations. 10+ passes with zero bugs → re-examine your rigor.
>
> ### Rule 6: SECTION-END VALIDATION
> After completing a section, run `python .github/skills/qa-tester/scripts/qa_validate_notes.py`.
> Re-execute any flagged test before moving to next section.

---

## Pipeline (strictly serial)

```
1. Pick ONE pending test (by ID order)
2. Set system state if needed
3. Run ONE command — WAIT for output
4. Verify ALL assertions from Expected Result vs ACTUAL output
5. Fix if needed (≤3 rounds)
6. ⛔ GATE: Edit .github/skills/qa-tester/QA_TEST_PROGRESS.md (row + counters) — ONE row per edit
7. Only NOW return to step 1
```

> **Environment**: Primary dev on **Linux** (AMD Ryzen AI 395). Use Bash syntax.
> Activate `.venv` before any `python` command: `source .venv/bin/activate`

---

## Step 1: Pick Target

1. Read `.github/skills/qa-tester/QA_TEST_PLAN.md` for test steps and expected results.
2. Read `.github/skills/qa-tester/QA_TEST_PROGRESS.md` for current status and phase.
3. User-specified section/ID → scope to that. Otherwise → first ⬜ pending test.
4. If any 🔧 tests exist, re-test those first.
5. Execute in section order (A→M), within section in ID order.
6. **Phase gating**: Check `Current Phase` in progress header. Skip tests whose Phase > current phase — mark ⏭️ with note `[SKIP] Phase N not yet implemented`.

### Test Categories

| Sections | Type | Execution Method |
|----------|------|-----------------|
| A | Infrastructure Health | Docker health + port checks via `qa_bootstrap.py status` |
| B | API Gateway | httpx/curl against FastAPI :8080 — see [references/test_patterns.md](references/test_patterns.md) |
| C | Security (JWT/RBAC/Rate Limit) | httpx with JWT tokens — see [references/test_patterns.md](references/test_patterns.md) |
| D | Agent Orchestrator | POST /api/v1/query → verify ReAct loop + tool calls in trace |
| E | Core Services | Inline pytest or direct Python calls |
| F | Retrieval & Storage | Milvus/Kùzu/Redis verification — see [references/test_patterns.md](references/test_patterns.md) |
| G | Ingestion Pipeline | POST /api/v1/documents/upload + Celery task monitoring |
| H | Model Services | Health endpoints :1234, :8001, :8002 |
| I | Gradio Frontend | HTTP requests to :7860 |
| J | Config & Fault Tolerance | `qa_config.py` profile switches → run tests → restore |
| K | Data Lifecycle | `qa_multistep.py <TEST_ID>` for multi-step flows |
| L | RAG Quality | Golden test set evaluation, compute Hit Rate/NDCG/MRR |
| M | Chunking & Evaluation | Pluggable chunking factory, strategy switching, evaluation harness |

See [references/phase_test_map.md](references/phase_test_map.md) for which sections are testable at each dev phase.

---

## Step 2: Set System State

| State | Command |
|-------|---------|
| InfraUp | `python .github/skills/qa-tester/scripts/qa_bootstrap.py infra` |
| ModelsUp | `python .github/skills/qa-tester/scripts/qa_bootstrap.py models` |
| Baseline | `python .github/skills/qa-tester/scripts/qa_bootstrap.py baseline` |
| Empty | `python .github/skills/qa-tester/scripts/qa_bootstrap.py clear` |
| InvalidLLM | `python .github/skills/qa-tester/scripts/qa_config.py apply invalid_llm` |
| InvalidEmbed | `python .github/skills/qa-tester/scripts/qa_config.py apply invalid_embed` |
| Any | no state change needed |

After config-profile tests → `python .github/skills/qa-tester/scripts/qa_config.py restore`
Check state → `python .github/skills/qa-tester/scripts/qa_bootstrap.py status`

---

## Step 3: Execute & Verify

### API Tests (B, C, D)

1. Read the test's **Steps** column from QA_TEST_PLAN.md.
2. Run httpx/curl command against FastAPI :8080.
3. Compare response against **Expected Result**:
   - **Health**: status=200, body contains service statuses
   - **Query**: status=200, body has `answer`, `citations`, `trace_id`
   - **Auth error**: status=401/403 with error message
   - **Rate limit**: status=429 after threshold

### Infrastructure Tests (A, H)

1. Run `qa_bootstrap.py status` or direct Docker/port checks.
2. Verify all services healthy, ports reachable.
3. For model services: check /health or /v1/models endpoints.

### Ingestion Tests (G)

1. POST document to /api/v1/documents/upload.
2. Poll task status via /api/v1/tasks/{task_id} until SUCCESS/FAILURE.
3. Verify chunks in Milvus, metadata in PostgreSQL, graph nodes in Kùzu.

See [references/test_patterns.md](references/test_patterns.md) for code templates.

### Storage Tests (F)

Use inline Python scripts to verify Milvus, Kùzu, Redis directly. Print concrete counts and values.

### Frontend Tests (I)

HTTP requests to Gradio :7860. Check page loads, API endpoints respond, SSE streaming works.

### Multi-Step Tests (K)

Tests with 3+ sequential steps **MUST** use the runner script:
```
python .github/skills/qa-tester/scripts/qa_multistep.py <TEST_ID>
```

The script executes every sub-step, prints ACTUAL values at each step, outputs `VERDICT: PASS/FAIL`. Copy the VERDICT and key step values into the Note.

### Config & Fault Tests (J)

1. Apply profile: `python .github/skills/qa-tester/scripts/qa_config.py apply <profile>`
2. Run command from test plan.
3. Verify error handling / graceful degradation.
4. Restore: `python .github/skills/qa-tester/scripts/qa_config.py restore`

### Chunking & Evaluation Tests (M)

1. Verify chunking factory creates correct strategy from settings.yaml.
2. Test each strategy (datasheet, fine, coarse, parent_child, semantic) produces valid chunks.
3. Run evaluation harness smoke tests: `python -m pytest tests/integration/test_chunking_strategies_smoke.py -q`
4. Verify strategy switching via `ingestion.chunking.strategy` in settings.yaml.
5. For multi-step evaluation tests, use `qa_multistep.py <TEST_ID>`.

---

## Step 4: Fix & Retry (≤3 rounds)

1. **Diagnose**: code bug / config issue / missing data / test plan error?
2. **Fix**: minimal change only. Record file/line in Note.
3. **Retry**: re-run same command.
4. After 3 failed rounds → mark ❌ with detailed notes.
5. If fix touches shared code → re-run previously-passed tests in same section.

---

## Step 5: Record Results

**⛔ GATE — do this BEFORE picking the next test.**

Edit `.github/skills/qa-tester/QA_TEST_PROGRESS.md`: update ONE test row + summary counters. ONE row per file edit.

### ✅ PASS Requirements

All must be true:
1. Ran the command **in this session**
2. Observed actual output **from that command**
3. Verified **every** assertion in Expected Result
4. Note contains **≥2 concrete values** from terminal output

### Note Format

```
<method>: <value_1>, <value_2>[, ...]
```

- **HTTP**: `status=200, body.answer_length=342, trace_id=abc123`
- **Docker**: `container=chipwise-postgres, health=healthy, port=5432`
- **Celery**: `task_id=xyz, state=SUCCESS, chunks=15`
- **CLI**: `exit=0, stdout: 'Total chunks: 15', source_file=stm32f407_datasheet.pdf`
- **Storage**: `milvus_entities=150, pg_rows=12, kuzu_nodes=6`
- **Multi-step**: `Step1: status=200, task_id=xyz. Step2: chunks=15. Step3: deleted=1. Step4: results=[]`
- **Bad** (BANNED): `"Already verified in C-02"`, `"Code uses yaml.safe_load"`, `"Should work because..."`

### Status Icons

| Icon | Meaning |
|------|---------|
| ✅ | Pass — all assertions verified against actual output |
| ❌ | Fail — failed after 3 fix attempts |
| ⏭️ | Skip — phase not implemented or missing external dependency |
| 🔧 | Fix applied — needs re-test |
| ⬜ | Pending — not yet tested |

### Counters

Update in the same edit: `✅ Pass: X | ❌ Fail: Y | ⏭️ Skip: Z | 🔧 Fix: W | ⬜ Pending: P` (must sum to Total).

### Section-End Gate

After each completed section:
```
python .github/skills/qa-tester/scripts/qa_validate_notes.py
```
Re-execute any flagged test. Do NOT proceed until 0 flags.

---

## Key Paths

| File | Purpose |
|------|---------|
| `.github/skills/qa-tester/QA_TEST_PLAN.md` | Test steps and expected results |
| `.github/skills/qa-tester/QA_TEST_PROGRESS.md` | Execution status and notes |
| `config/settings.yaml` | System configuration |
| `src/api/main.py` | FastAPI application entry point |
| `src/agent/orchestrator.py` | Agent ReAct loop |
| `src/ingestion/tasks.py` | Celery ingestion task chain |
| `src/ingestion/chunking/factory.py` | Pluggable chunking strategy factory |
| `src/ingestion/chunking/base.py` | BaseChunker ABC for all strategies |
| `evaluation/chunking/runner.py` | CLI runner for chunking evaluation harness |
| `tests/fixtures/sample_documents/` | Test chip datasheets |
| `tests/fixtures/golden_test_set.json` | RAG evaluation golden set (100+ QA pairs) |
| `tests/fixtures/golden_retrieval_qrels.jsonl` | Retrieval qrels for chunking evaluation |

## Service Ports

FastAPI 8080 | LM Studio 1234 | BGE-M3 8001 | bce-reranker 8002 | PostgreSQL 5432 | Milvus 19530 | Redis 6379 | Kùzu embedded | Gradio 7860

## Test Documents

| File | Description |
|------|------------|
| `stm32f407_datasheet.pdf` | STM32F407 datasheet (~50 pages, tables, diagrams) |
| `stm32f103_datasheet.pdf` | STM32F103 for chip comparison tests |
| `sample_bom.xlsx` | BOM review test fixture |
| `simple_test.pdf` | Minimal 1-page doc for smoke tests |

All in `tests/fixtures/sample_documents/`.
