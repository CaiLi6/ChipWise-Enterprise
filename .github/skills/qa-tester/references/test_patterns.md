# Test Patterns — ChipWise Enterprise

Code templates for each test type. Copy and adapt per test case.

---

## FastAPI — httpx (Live Server)

```python
import httpx

# Health check
resp = httpx.get("http://localhost:8080/health", timeout=10)
print(f"status={resp.status_code}, body={resp.json()}")

# Readiness (dependency status)
resp = httpx.get("http://localhost:8080/readiness", timeout=10)
print(f"status={resp.status_code}, services={resp.json()}")

# Query with JWT
token = "Bearer <JWT_TOKEN>"
resp = httpx.post(
    "http://localhost:8080/api/v1/query",
    json={"query": "What are STM32F407 GPIO specs?", "session_id": "test-001"},
    headers={"Authorization": token},
    timeout=60,
)
print(f"status={resp.status_code}, answer_len={len(resp.json().get('answer',''))}, trace_id={resp.json().get('trace_id')}")

# Unauthenticated request (expect 401)
resp = httpx.post("http://localhost:8080/api/v1/query", json={"query": "test"}, timeout=10)
print(f"status={resp.status_code}, error={resp.json().get('detail')}")
```

---

## FastAPI — curl (Shell)

```bash
# Health
curl -s http://localhost:8080/health | python -m json.tool

# Query
curl -s -X POST http://localhost:8080/api/v1/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -d '{"query": "Compare STM32F407 and STM32F103", "session_id": "test-002"}' | python -m json.tool
```

---

## JWT Token Generation (Test Only)

```python
import jwt, time

# HS256 (dev/test fallback)
secret = "test-jwt-secret-key"
payload = {"sub": "test_user", "roles": ["user"], "exp": int(time.time()) + 3600}
token = jwt.encode(payload, secret, algorithm="HS256")
print(f"token={token[:40]}...")

# Admin token
admin_payload = {"sub": "admin_user", "roles": ["admin"], "exp": int(time.time()) + 3600}
admin_token = jwt.encode(admin_payload, secret, algorithm="HS256")

# Expired token
expired_payload = {"sub": "test_user", "roles": ["user"], "exp": int(time.time()) - 60}
expired_token = jwt.encode(expired_payload, secret, algorithm="HS256")
```

---

## Rate Limit Hammering

```python
import httpx

url = "http://localhost:8080/api/v1/query"
headers = {"Authorization": "Bearer <TOKEN>"}
body = {"query": "test", "session_id": "rate-limit-test"}

results = []
for i in range(35):
    r = httpx.post(url, json=body, headers=headers, timeout=10)
    results.append(r.status_code)

passed = sum(1 for s in results if s == 200)
blocked = sum(1 for s in results if s == 429)
print(f"total={len(results)}, passed={passed}, blocked_429={blocked}")
# Expect: first ~30 pass, remaining return 429
```

---

## Document Upload & Celery Task Monitoring

```python
import httpx, time

# Upload document → get task_id
with open("tests/fixtures/sample_documents/simple_test.pdf", "rb") as f:
    resp = httpx.post(
        "http://localhost:8080/api/v1/documents/upload",
        files={"file": ("simple_test.pdf", f, "application/pdf")},
        headers={"Authorization": "Bearer <TOKEN>"},
        timeout=30,
    )
task_id = resp.json()["task_id"]
print(f"upload: status={resp.status_code}, task_id={task_id}")

# Poll until done
for attempt in range(60):
    status_resp = httpx.get(
        f"http://localhost:8080/api/v1/tasks/{task_id}",
        headers={"Authorization": "Bearer <TOKEN>"},
        timeout=10,
    )
    state = status_resp.json()["state"]
    if state in ("SUCCESS", "FAILURE"):
        print(f"task: state={state}, result={status_resp.json()}")
        break
    time.sleep(5)
```

---

## Docker Health Checks

```python
import subprocess

# Container health
services = ["chipwise-postgres", "chipwise-milvus", "chipwise-redis"]
for svc in services:
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Health.Status}}", svc],
        capture_output=True, text=True,
    )
    print(f"{svc}: health={result.stdout.strip()}")
```

```bash
# Port checks (shell)
curl -sf http://localhost:8080/health && echo "FastAPI OK" || echo "FastAPI DOWN"
curl -sf http://localhost:1234/v1/models && echo "LM Studio OK" || echo "LM Studio DOWN"
curl -sf http://localhost:8001/health && echo "BGE-M3 OK" || echo "BGE-M3 DOWN"
curl -sf http://localhost:8002/health && echo "bce-reranker OK" || echo "bce-reranker DOWN"
docker exec chipwise-postgres pg_isready && echo "PostgreSQL OK" || echo "PostgreSQL DOWN"
docker exec chipwise-redis redis-cli ping && echo "Redis OK" || echo "Redis DOWN"
```

---

## Milvus Verification

```python
from pymilvus import connections, Collection

connections.connect(host="localhost", port="19530")
col = Collection("datasheet_chunks")
col.load()

# Count entities
print(f"entities={col.num_entities}")

# Query by document_id
results = col.query(
    expr='document_id == "stm32f407"',
    output_fields=["chunk_text", "source_file"],
    limit=5,
)
print(f"query_results={len(results)}, first_source={results[0]['source_file'] if results else 'none'}")

# Delete by document_id
col.delete(expr='document_id == "stm32f407"')
print(f"after_delete={col.num_entities}")
```

---

## Kùzu Graph Verification

```python
import kuzu

db = kuzu.Database("data/kuzu")
conn = kuzu.Connection(db)

# Count chip nodes
result = conn.execute("MATCH (c:Chip) RETURN count(c) AS cnt")
while result.has_next():
    print(f"chip_count={result.get_next()[0]}")

# Query chip parameters
result = conn.execute(
    "MATCH (c:Chip)-[:HAS_PARAMETER]->(p:Parameter) "
    "WHERE c.part_number = 'STM32F407' RETURN p.name, p.value LIMIT 5"
)
while result.has_next():
    row = result.get_next()
    print(f"param: name={row[0]}, value={row[1]}")

# Count all node tables
for table in ["Chip", "Parameter", "Errata", "Document", "DesignRule", "Peripheral"]:
    result = conn.execute(f"MATCH (n:{table}) RETURN count(n) AS cnt")
    while result.has_next():
        print(f"{table}_count={result.get_next()[0]}")
```

---

## Redis Verification

```python
import redis

r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
print(f"ping={r.ping()}")

# Key namespace counts
for pattern, label in [("session:*", "sessions"), ("gptcache:*", "cache"), ("ratelimit:*", "ratelimit")]:
    keys = r.keys(pattern)
    print(f"{label}_count={len(keys)}")

# Celery broker (DB 1)
r1 = redis.Redis(host="localhost", port=6379, db=1, decode_responses=True)
print(f"celery_ping={r1.ping()}")
```

---

## PostgreSQL Verification

```python
import psycopg2

conn = psycopg2.connect(host="localhost", port=5432, dbname="chipwise", user="chipwise", password="<PG_PASSWORD>")
cur = conn.cursor()

for table in ["chips", "parameters", "documents", "chunks", "errata"]:
    cur.execute(f"SELECT count(*) FROM {table}")
    print(f"{table}_rows={cur.fetchone()[0]}")

cur.close()
conn.close()
```

---

## LM Studio Model Check

```python
import httpx

# List loaded models
resp = httpx.get("http://localhost:1234/v1/models", timeout=10)
models = [m["id"] for m in resp.json()["data"]]
print(f"models={models}")

# Chat completion (primary)
resp = httpx.post("http://localhost:1234/v1/chat/completions", json={
    "model": models[0],
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 50,
}, timeout=30)
print(f"primary: status={resp.status_code}, tokens={resp.json()['usage']['completion_tokens']}")
```

---

## Gradio Frontend

```python
import httpx

# Page loads
resp = httpx.get("http://localhost:7860/", timeout=10)
print(f"gradio: status={resp.status_code}, content_length={len(resp.content)}")

# Gradio API predict endpoint
resp = httpx.post(
    "http://localhost:7860/api/predict",
    json={"data": ["What are STM32F407 GPIO specs?"]},
    timeout=60,
)
print(f"predict: status={resp.status_code}, response_length={len(resp.json().get('data', [''])[0])}")
```
