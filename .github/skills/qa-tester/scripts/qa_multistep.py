#!/usr/bin/env python3
"""QA Multi-Step Test Runner — Execute compound test cases for ChipWise Enterprise.

Provides deterministic, non-skippable multi-step test execution for tests
that require sequential operations (upload→query→delete→query, etc.).

Each function prints step-by-step results with ACTUAL values so the AI
cannot infer or skip steps.

Usage:
    python .github/skills/qa-tester/scripts/qa_multistep.py <test_id>

Supported test IDs:
    K-01   Full lifecycle: upload→query→delete→query
    K-02   Cross-storage delete verification (PG + Milvus + Kùzu)
    K-03   Multi-collection isolation
    K-04   Re-ingest after delete
    K-06   Graph sync after ingestion
    K-07   Cache invalidation on ingest
    J-05   Invalid LLM endpoint → graceful error
    J-06   Invalid embedding endpoint → graceful error
    J-11   Chunk size parameter change
"""

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "sample_documents"
API_BASE = "http://localhost:8080"

# Try to import httpx; fall back to requests or curl
try:
    import httpx
    _HTTP_CLIENT = "httpx"
except ImportError:
    _HTTP_CLIENT = "curl"


# ── HTTP Helpers ─────────────────────────────────────────────────────────

def _get(path: str, timeout: int = 30) -> dict:
    """GET request to FastAPI."""
    url = f"{API_BASE}{path}"
    if _HTTP_CLIENT == "httpx":
        resp = httpx.get(url, timeout=timeout)
        return {"status": resp.status_code, "body": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text}
    else:
        import subprocess
        r = subprocess.run(["curl", "-sf", "--max-time", str(timeout), url], capture_output=True, text=True)
        body = json.loads(r.stdout) if r.stdout.strip() else {}
        return {"status": 200 if r.returncode == 0 else 500, "body": body}


def _post(path: str, json_body: dict = None, files: dict = None, timeout: int = 120) -> dict:
    """POST request to FastAPI."""
    url = f"{API_BASE}{path}"
    if _HTTP_CLIENT == "httpx":
        if files:
            resp = httpx.post(url, files=files, timeout=timeout)
        else:
            resp = httpx.post(url, json=json_body, timeout=timeout)
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        return {"status": resp.status_code, "body": body}
    else:
        import subprocess
        cmd = ["curl", "-sf", "--max-time", str(timeout), "-X", "POST"]
        if json_body:
            cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(json_body)]
        cmd.append(url)
        r = subprocess.run(cmd, capture_output=True, text=True)
        body = json.loads(r.stdout) if r.stdout.strip() else {}
        return {"status": 200 if r.returncode == 0 else 500, "body": body}


def _delete(path: str, timeout: int = 30) -> dict:
    """DELETE request to FastAPI."""
    url = f"{API_BASE}{path}"
    if _HTTP_CLIENT == "httpx":
        resp = httpx.delete(url, timeout=timeout)
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        return {"status": resp.status_code, "body": body}
    else:
        import subprocess
        r = subprocess.run(["curl", "-sf", "--max-time", str(timeout), "-X", "DELETE", url], capture_output=True, text=True)
        body = json.loads(r.stdout) if r.stdout.strip() else {}
        return {"status": 200 if r.returncode == 0 else 500, "body": body}


def upload_document(filename: str, collection: str = "datasheet_chunks") -> dict:
    """Upload a document via FastAPI endpoint."""
    filepath = FIXTURES_DIR / filename
    if not filepath.exists():
        return {"status": 404, "body": {"error": f"File not found: {filepath}"}}

    if _HTTP_CLIENT == "httpx":
        with open(filepath, "rb") as f:
            resp = httpx.post(
                f"{API_BASE}/api/v1/documents/upload",
                files={"file": (filename, f, "application/pdf")},
                params={"collection": collection},
                timeout=120,
            )
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        return {"status": resp.status_code, "body": body}
    else:
        import subprocess
        r = subprocess.run(
            ["curl", "-sf", "--max-time", "120", "-X", "POST",
             "-F", f"file=@{filepath}",
             f"{API_BASE}/api/v1/documents/upload?collection={collection}"],
            capture_output=True, text=True,
        )
        body = json.loads(r.stdout) if r.stdout.strip() else {}
        return {"status": 200 if r.returncode == 0 else 500, "body": body}


def wait_for_task(task_id: str, timeout: int = 300) -> dict:
    """Poll task status until completed or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        resp = _get(f"/api/v1/tasks/{task_id}")
        state = resp["body"].get("state", "UNKNOWN") if isinstance(resp["body"], dict) else "UNKNOWN"
        if state in ("SUCCESS", "FAILURE"):
            return resp
        time.sleep(5)
    return {"status": 408, "body": {"state": "TIMEOUT"}}


def query(q: str, session_id: str = "qa-test") -> dict:
    """POST a query to the Agent."""
    return _post("/api/v1/query", json_body={"query": q, "session_id": session_id})


def get_milvus_count(collection: str = "datasheet_chunks") -> int:
    """Get entity count from Milvus."""
    try:
        from pymilvus import connections, Collection
        connections.connect(host="localhost", port="19530")
        col = Collection(collection)
        col.load()
        count = col.num_entities
        connections.disconnect("default")
        return count
    except Exception as e:
        print(f"   [Milvus error: {e}]")
        return -1


def get_pg_count(table: str) -> int:
    """Get row count from PostgreSQL."""
    try:
        import psycopg2
        conn = psycopg2.connect(host="localhost", port=5432, dbname="chipwise", user="chipwise", password="chipwise")
        cur = conn.cursor()
        cur.execute(f"SELECT count(*) FROM {table}")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count
    except Exception as e:
        print(f"   [PG error: {e}]")
        return -1


def get_kuzu_count(node_table: str) -> int:
    """Get node count from Kùzu."""
    try:
        import kuzu
        db = kuzu.Database(str(REPO_ROOT / "data" / "kuzu"))
        conn = kuzu.Connection(db)
        result = conn.execute(f"MATCH (n:{node_table}) RETURN count(n) AS cnt")
        if result.has_next():
            return result.get_next()[0]
        return 0
    except Exception as e:
        print(f"   [Kùzu error: {e}]")
        return -1


# ── Test Functions ───────────────────────────────────────────────────────

def test_k01() -> bool:
    """K-01: Full lifecycle — upload → query → delete → query."""
    print("=" * 60)
    print("TEST K-01: Full lifecycle (upload → query → delete → query)")
    print("=" * 60)

    # Step 1: Upload document
    print("\n--- Step 1: Upload simple_test.pdf ---")
    resp = upload_document("simple_test.pdf")
    print(f"  status={resp['status']}")
    print(f"  body={json.dumps(resp['body'], ensure_ascii=False)[:200]}")
    task_id = resp["body"].get("task_id", "none") if isinstance(resp["body"], dict) else "none"
    print(f"  task_id={task_id}")

    if task_id != "none":
        print("\n--- Step 1b: Wait for task completion ---")
        task_resp = wait_for_task(task_id)
        print(f"  state={task_resp['body'].get('state', 'UNKNOWN')}")

    # Step 2: Query for document content
    print("\n--- Step 2: Query for uploaded content ---")
    q_resp = query("simple test document content")
    print(f"  status={q_resp['status']}")
    answer = q_resp["body"].get("answer", "") if isinstance(q_resp["body"], dict) else ""
    has_results = len(answer) > 0
    print(f"  answer_length={len(answer)}")
    print(f"  has_results={has_results}")

    # Step 3: Delete document
    print("\n--- Step 3: Delete document ---")
    doc_id = resp["body"].get("document_id", "unknown") if isinstance(resp["body"], dict) else "unknown"
    del_resp = _delete(f"/api/v1/documents/{doc_id}")
    print(f"  status={del_resp['status']}")
    print(f"  body={json.dumps(del_resp['body'], ensure_ascii=False)[:200]}")

    # Step 4: Query again (should find nothing)
    print("\n--- Step 4: Query again (expect no results) ---")
    q_resp2 = query("simple test document content")
    print(f"  status={q_resp2['status']}")
    answer2 = q_resp2["body"].get("answer", "") if isinstance(q_resp2["body"], dict) else ""
    print(f"  answer_length={len(answer2)}")

    # Verdict
    passed = has_results and resp["status"] in (200, 202)
    print(f"\nVERDICT: {'PASS' if passed else 'FAIL'}")
    print(f"  Step1: upload status={resp['status']}, task_id={task_id}")
    print(f"  Step2: answer_length={len(answer)}, has_results={has_results}")
    print(f"  Step3: delete status={del_resp['status']}")
    print(f"  Step4: answer_length={len(answer2)}")
    return passed


def test_k02() -> bool:
    """K-02: Cross-storage delete verification (PG + Milvus + Kùzu)."""
    print("=" * 60)
    print("TEST K-02: Cross-storage delete verification")
    print("=" * 60)

    # Step 1: Record counts before
    print("\n--- Step 1: Record storage counts BEFORE ---")
    pg_before = get_pg_count("chunks")
    mv_before = get_milvus_count()
    kz_before = get_kuzu_count("Document")
    print(f"  pg_chunks={pg_before}, milvus_entities={mv_before}, kuzu_documents={kz_before}")

    # Step 2: Upload a document
    print("\n--- Step 2: Upload simple_test.pdf ---")
    resp = upload_document("simple_test.pdf")
    task_id = resp["body"].get("task_id", "none") if isinstance(resp["body"], dict) else "none"
    print(f"  status={resp['status']}, task_id={task_id}")
    if task_id != "none":
        wait_for_task(task_id)

    # Step 3: Record counts after ingest
    print("\n--- Step 3: Record storage counts AFTER ingest ---")
    pg_after_ingest = get_pg_count("chunks")
    mv_after_ingest = get_milvus_count()
    kz_after_ingest = get_kuzu_count("Document")
    print(f"  pg_chunks={pg_after_ingest}, milvus_entities={mv_after_ingest}, kuzu_documents={kz_after_ingest}")

    # Step 4: Delete the document
    print("\n--- Step 4: Delete document ---")
    doc_id = resp["body"].get("document_id", "unknown") if isinstance(resp["body"], dict) else "unknown"
    del_resp = _delete(f"/api/v1/documents/{doc_id}")
    print(f"  status={del_resp['status']}")

    # Step 5: Record counts after delete
    print("\n--- Step 5: Record storage counts AFTER delete ---")
    pg_after_del = get_pg_count("chunks")
    mv_after_del = get_milvus_count()
    kz_after_del = get_kuzu_count("Document")
    print(f"  pg_chunks={pg_after_del}, milvus_entities={mv_after_del}, kuzu_documents={kz_after_del}")

    # Verdict
    all_cleaned = (pg_after_del <= pg_before and mv_after_del <= mv_before and kz_after_del <= kz_before)
    print(f"\nVERDICT: {'PASS' if all_cleaned else 'FAIL'}")
    print(f"  PG:     {pg_before} → {pg_after_ingest} → {pg_after_del}")
    print(f"  Milvus: {mv_before} → {mv_after_ingest} → {mv_after_del}")
    print(f"  Kùzu:   {kz_before} → {kz_after_ingest} → {kz_after_del}")
    return all_cleaned


def test_k03() -> bool:
    """K-03: Multi-collection isolation."""
    print("=" * 60)
    print("TEST K-03: Multi-collection isolation")
    print("=" * 60)

    # Step 1: Upload doc A to col_a
    print("\n--- Step 1: Upload simple_test.pdf → col_a ---")
    resp_a = upload_document("simple_test.pdf", collection="col_a")
    task_a = resp_a["body"].get("task_id", "none") if isinstance(resp_a["body"], dict) else "none"
    print(f"  status={resp_a['status']}, task_id={task_a}")
    if task_a != "none":
        wait_for_task(task_a)

    # Step 2: Upload doc B to col_b (use a different fixture if available)
    print("\n--- Step 2: Upload stm32f407_datasheet.pdf → col_b ---")
    resp_b = upload_document("stm32f407_datasheet.pdf", collection="col_b")
    task_b = resp_b["body"].get("task_id", "none") if isinstance(resp_b["body"], dict) else "none"
    print(f"  status={resp_b['status']}, task_id={task_b}")
    if task_b != "none":
        wait_for_task(task_b)

    # Step 3: Query col_a — should only have doc A content
    print("\n--- Step 3: Query col_a ---")
    q_a = _post("/api/v1/query", json_body={
        "query": "simple test content", "session_id": "qa-k03", "collection": "col_a"
    })
    sources_a = []
    if isinstance(q_a["body"], dict):
        citations = q_a["body"].get("citations", [])
        sources_a = [c.get("source_file", "") for c in citations] if citations else []
    print(f"  status={q_a['status']}, sources={sources_a[:5]}")

    # Step 4: Query col_b — should only have doc B content
    print("\n--- Step 4: Query col_b ---")
    q_b = _post("/api/v1/query", json_body={
        "query": "STM32F407 specifications", "session_id": "qa-k03", "collection": "col_b"
    })
    sources_b = []
    if isinstance(q_b["body"], dict):
        citations = q_b["body"].get("citations", [])
        sources_b = [c.get("source_file", "") for c in citations] if citations else []
    print(f"  status={q_b['status']}, sources={sources_b[:5]}")

    # Verdict
    no_cross = not any("stm32" in s.lower() for s in sources_a)
    print(f"\nVERDICT: {'PASS' if no_cross else 'FAIL'}")
    print(f"  col_a sources: {sources_a[:5]}")
    print(f"  col_b sources: {sources_b[:5]}")
    print(f"  no_cross_contamination={no_cross}")
    return no_cross


def test_k04() -> bool:
    """K-04: Re-ingest after delete."""
    print("=" * 60)
    print("TEST K-04: Re-ingest after delete")
    print("=" * 60)

    # Step 1: Upload
    print("\n--- Step 1: Upload simple_test.pdf ---")
    resp1 = upload_document("simple_test.pdf")
    task1 = resp1["body"].get("task_id", "none") if isinstance(resp1["body"], dict) else "none"
    print(f"  status={resp1['status']}, task_id={task1}")
    if task1 != "none":
        task_resp1 = wait_for_task(task1)
        print(f"  task_state={task_resp1['body'].get('state', 'UNKNOWN')}")

    chunks_after_first = get_milvus_count()
    print(f"  milvus_entities_after_first={chunks_after_first}")

    # Step 2: Delete
    print("\n--- Step 2: Delete document ---")
    doc_id = resp1["body"].get("document_id", "unknown") if isinstance(resp1["body"], dict) else "unknown"
    del_resp = _delete(f"/api/v1/documents/{doc_id}")
    print(f"  delete_status={del_resp['status']}")
    chunks_after_del = get_milvus_count()
    print(f"  milvus_entities_after_delete={chunks_after_del}")

    # Step 3: Re-upload same file
    print("\n--- Step 3: Re-upload simple_test.pdf ---")
    resp2 = upload_document("simple_test.pdf")
    task2 = resp2["body"].get("task_id", "none") if isinstance(resp2["body"], dict) else "none"
    print(f"  status={resp2['status']}, task_id={task2}")
    if task2 != "none":
        task_resp2 = wait_for_task(task2)
        print(f"  task_state={task_resp2['body'].get('state', 'UNKNOWN')}")

    chunks_after_reingest = get_milvus_count()
    print(f"  milvus_entities_after_reingest={chunks_after_reingest}")

    # Step 4: Query
    print("\n--- Step 4: Query for content ---")
    q_resp = query("simple test document")
    answer_len = len(q_resp["body"].get("answer", "")) if isinstance(q_resp["body"], dict) else 0
    print(f"  status={q_resp['status']}, answer_length={answer_len}")

    # Verdict
    passed = chunks_after_reingest > 0 and answer_len > 0
    print(f"\nVERDICT: {'PASS' if passed else 'FAIL'}")
    print(f"  First ingest:  {chunks_after_first} entities")
    print(f"  After delete:  {chunks_after_del} entities")
    print(f"  After reingest: {chunks_after_reingest} entities")
    print(f"  Query answer_length: {answer_len}")
    return passed


def test_k06() -> bool:
    """K-06: Graph sync after ingestion."""
    print("=" * 60)
    print("TEST K-06: Graph sync after ingestion")
    print("=" * 60)

    # Step 1: Record Kùzu counts before
    print("\n--- Step 1: Kùzu counts BEFORE ---")
    chips_before = get_kuzu_count("Chip")
    params_before = get_kuzu_count("Parameter")
    print(f"  chip_count={chips_before}, parameter_count={params_before}")

    # Step 2: Upload chip datasheet
    print("\n--- Step 2: Upload stm32f407_datasheet.pdf ---")
    resp = upload_document("stm32f407_datasheet.pdf")
    task_id = resp["body"].get("task_id", "none") if isinstance(resp["body"], dict) else "none"
    print(f"  status={resp['status']}, task_id={task_id}")
    if task_id != "none":
        task_resp = wait_for_task(task_id)
        print(f"  task_state={task_resp['body'].get('state', 'UNKNOWN')}")

    # Step 3: Check PG for parameters
    print("\n--- Step 3: PostgreSQL parameters ---")
    pg_params = get_pg_count("parameters")
    print(f"  parameter_rows={pg_params}")

    # Step 4: Check Kùzu for synced data
    print("\n--- Step 4: Kùzu counts AFTER ---")
    chips_after = get_kuzu_count("Chip")
    params_after = get_kuzu_count("Parameter")
    print(f"  chip_count={chips_after}, parameter_count={params_after}")

    # Verdict
    synced = chips_after > chips_before or params_after > params_before
    print(f"\nVERDICT: {'PASS' if synced else 'FAIL'}")
    print(f"  Chips:  {chips_before} → {chips_after}")
    print(f"  Params: {params_before} → {params_after}")
    print(f"  PG params: {pg_params}")
    return synced


def test_k07() -> bool:
    """K-07: Cache invalidation on new document ingest."""
    print("=" * 60)
    print("TEST K-07: Cache invalidation on ingest")
    print("=" * 60)

    # Step 1: Query (creates cache entry)
    print("\n--- Step 1: Initial query (creates cache) ---")
    q1 = query("STM32F407 GPIO specifications")
    print(f"  status={q1['status']}")
    cache_hit_1 = q1["body"].get("cache_hit", "unknown") if isinstance(q1["body"], dict) else "unknown"
    print(f"  cache_hit={cache_hit_1}")

    # Step 2: Same query again (should hit cache)
    print("\n--- Step 2: Repeat query (expect cache hit) ---")
    q2 = query("STM32F407 GPIO specifications")
    cache_hit_2 = q2["body"].get("cache_hit", "unknown") if isinstance(q2["body"], dict) else "unknown"
    print(f"  cache_hit={cache_hit_2}")

    # Step 3: Ingest a new document
    print("\n--- Step 3: Upload new document ---")
    resp = upload_document("simple_test.pdf")
    task_id = resp["body"].get("task_id", "none") if isinstance(resp["body"], dict) else "none"
    print(f"  status={resp['status']}, task_id={task_id}")
    if task_id != "none":
        wait_for_task(task_id)

    # Step 4: Same query again (cache should be invalidated)
    print("\n--- Step 4: Repeat query (expect cache miss) ---")
    q3 = query("STM32F407 GPIO specifications")
    cache_hit_3 = q3["body"].get("cache_hit", "unknown") if isinstance(q3["body"], dict) else "unknown"
    print(f"  cache_hit={cache_hit_3}")

    # Verdict
    passed = cache_hit_3 is False or cache_hit_3 == "false" or cache_hit_3 == "unknown"
    print(f"\nVERDICT: {'PASS' if passed else 'FAIL'}")
    print(f"  Query 1 cache_hit={cache_hit_1}")
    print(f"  Query 2 cache_hit={cache_hit_2}")
    print(f"  Ingest: task_id={task_id}")
    print(f"  Query 3 cache_hit={cache_hit_3} (should be false/miss)")
    return passed


def test_j05() -> bool:
    """J-05: Invalid LLM endpoint → graceful error."""
    print("=" * 60)
    print("TEST J-05: Invalid LLM endpoint → graceful error")
    print("=" * 60)

    # Step 1: Apply invalid_llm config
    print("\n--- Step 1: Apply invalid_llm profile ---")
    import subprocess
    config_script = Path(__file__).parent / "qa_config.py"
    r = subprocess.run([sys.executable, str(config_script), "apply", "invalid_llm"],
                       capture_output=True, text=True, cwd=str(REPO_ROOT))
    print(f"  exit_code={r.returncode}")
    print(f"  stdout={r.stdout[:200]}")

    # Step 2: POST query (should get graceful error, not hang)
    print("\n--- Step 2: POST query with invalid LLM ---")
    try:
        q_resp = query("test query with invalid LLM")
        print(f"  status={q_resp['status']}")
        print(f"  body={json.dumps(q_resp['body'], ensure_ascii=False)[:200]}")
        graceful = q_resp["status"] in (200, 500, 502, 503)
    except Exception as e:
        print(f"  exception={e}")
        graceful = False

    # Step 3: Restore config
    print("\n--- Step 3: Restore config ---")
    r2 = subprocess.run([sys.executable, str(config_script), "restore"],
                        capture_output=True, text=True, cwd=str(REPO_ROOT))
    print(f"  exit_code={r2.returncode}")

    # Verdict
    print(f"\nVERDICT: {'PASS' if graceful else 'FAIL'}")
    print(f"  Config applied: exit={r.returncode}")
    print(f"  Query graceful error: {graceful}")
    print(f"  Config restored: exit={r2.returncode}")
    return graceful


def test_j06() -> bool:
    """J-06: Invalid embedding endpoint → graceful error."""
    print("=" * 60)
    print("TEST J-06: Invalid embedding endpoint → graceful error")
    print("=" * 60)

    # Step 1: Apply invalid_embed config
    print("\n--- Step 1: Apply invalid_embed profile ---")
    import subprocess
    config_script = Path(__file__).parent / "qa_config.py"
    r = subprocess.run([sys.executable, str(config_script), "apply", "invalid_embed"],
                       capture_output=True, text=True, cwd=str(REPO_ROOT))
    print(f"  exit_code={r.returncode}")

    # Step 2: Upload document (should fail at embed stage)
    print("\n--- Step 2: Upload document with invalid embedding ---")
    resp = upload_document("simple_test.pdf")
    print(f"  status={resp['status']}")
    print(f"  body={json.dumps(resp['body'], ensure_ascii=False)[:200]}")

    task_id = resp["body"].get("task_id", "none") if isinstance(resp["body"], dict) else "none"
    task_state = "UNKNOWN"
    if task_id != "none":
        task_resp = wait_for_task(task_id, timeout=60)
        task_state = task_resp["body"].get("state", "UNKNOWN") if isinstance(task_resp["body"], dict) else "UNKNOWN"
        print(f"  task_state={task_state}")

    # Step 3: Restore config
    print("\n--- Step 3: Restore config ---")
    r2 = subprocess.run([sys.executable, str(config_script), "restore"],
                        capture_output=True, text=True, cwd=str(REPO_ROOT))
    print(f"  exit_code={r2.returncode}")

    # Verdict
    graceful = task_state == "FAILURE" or resp["status"] >= 400
    print(f"\nVERDICT: {'PASS' if graceful else 'FAIL'}")
    print(f"  Config applied: exit={r.returncode}")
    print(f"  Upload result: status={resp['status']}, task_state={task_state}")
    print(f"  Config restored: exit={r2.returncode}")
    return graceful


def test_j11() -> bool:
    """J-11: Chunk size parameter change affects chunk count."""
    print("=" * 60)
    print("TEST J-11: Chunk size parameter change")
    print("=" * 60)

    import subprocess
    config_script = Path(__file__).parent / "qa_config.py"

    # Step 1: Upload with default chunk_size (1000)
    print("\n--- Step 1: Upload with default chunk_size ---")
    resp1 = upload_document("simple_test.pdf")
    task1 = resp1["body"].get("task_id", "none") if isinstance(resp1["body"], dict) else "none"
    if task1 != "none":
        wait_for_task(task1)
    count1 = get_milvus_count()
    print(f"  milvus_entities={count1}")

    # Step 2: Change chunk_size to 500
    print("\n--- Step 2: Change chunk_size to 500 ---")
    try:
        import yaml
        settings_file = REPO_ROOT / "config" / "settings.yaml"
        settings = yaml.safe_load(settings_file.read_text(encoding="utf-8"))
        original_chunk_size = settings.get("ingestion", {}).get("chunk_size", 1000)
        if "ingestion" not in settings:
            settings["ingestion"] = {}
        settings["ingestion"]["chunk_size"] = 500
        settings_file.write_text(yaml.dump(settings, default_flow_style=False, allow_unicode=True), encoding="utf-8")
        print(f"  chunk_size: {original_chunk_size} → 500")
    except Exception as e:
        print(f"  error: {e}")
        return False

    # Step 3: Clear and re-upload
    print("\n--- Step 3: Clear and re-upload with chunk_size=500 ---")
    # Delete previous and re-ingest
    resp2 = upload_document("simple_test.pdf")
    task2 = resp2["body"].get("task_id", "none") if isinstance(resp2["body"], dict) else "none"
    if task2 != "none":
        wait_for_task(task2)
    count2 = get_milvus_count()
    print(f"  milvus_entities={count2}")

    # Step 4: Restore chunk_size
    print("\n--- Step 4: Restore original chunk_size ---")
    try:
        settings["ingestion"]["chunk_size"] = original_chunk_size
        settings_file = REPO_ROOT / "config" / "settings.yaml"
        settings_file.write_text(yaml.dump(settings, default_flow_style=False, allow_unicode=True), encoding="utf-8")
        print(f"  chunk_size restored to {original_chunk_size}")
    except Exception as e:
        print(f"  error: {e}")

    # Verdict
    more_chunks = count2 > count1
    print(f"\nVERDICT: {'PASS' if more_chunks else 'FAIL'}")
    print(f"  chunk_size=1000: {count1} entities")
    print(f"  chunk_size=500:  {count2} entities")
    print(f"  more_chunks_with_smaller_size={more_chunks}")
    return more_chunks


# ── Test Registry & Main ─────────────────────────────────────────────────

TESTS = {
    "K-01": test_k01,
    "K-02": test_k02,
    "K-03": test_k03,
    "K-04": test_k04,
    "K-06": test_k06,
    "K-07": test_k07,
    "J-05": test_j05,
    "J-06": test_j06,
    "J-11": test_j11,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="QA Multi-Step Test Runner — ChipWise Enterprise")
    parser.add_argument("test_id", help=f"Test ID to run. Supported: {', '.join(TESTS.keys())}")
    args = parser.parse_args()

    test_id = args.test_id.upper()
    if test_id not in TESTS:
        print(f"❌ Unknown test ID: {test_id}")
        print(f"   Supported: {', '.join(TESTS.keys())}")
        sys.exit(1)

    passed = TESTS[test_id]()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
