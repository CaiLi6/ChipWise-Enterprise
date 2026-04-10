#!/usr/bin/env python3
"""QA Bootstrap — Set up / tear down system states for ChipWise Enterprise QA testing.

Usage:
    python .github/skills/qa-tester/scripts/qa_bootstrap.py [command]

Commands:
    infra      Verify Docker containers healthy (PG, Milvus, Redis), run schema init
    models     Verify model services (LM Studio, BGE-M3, bce-reranker) are responding
    baseline   Full setup: infra + models + seed documents + baseline queries
    clear      Clear all data → Empty state (truncate PG, flush Milvus/Redis, clear Kùzu)
    status     Show current system state (service health + data counts)
"""

import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "sample_documents"
DATA_DIR = REPO_ROOT / "data"
LOGS_DIR = REPO_ROOT / "logs"
TRACES_FILE = LOGS_DIR / "traces.jsonl"
SETTINGS_FILE = REPO_ROOT / "config" / "settings.yaml"

# Service endpoints
SERVICES = {
    "postgres":    {"host": "localhost", "port": 5432,  "type": "tcp"},
    "milvus":      {"host": "localhost", "port": 19530, "type": "tcp"},
    "redis":       {"host": "localhost", "port": 6379,  "type": "tcp"},
    "fastapi":     {"host": "localhost", "port": 8080,  "type": "http", "path": "/health"},
    "lm_studio":   {"host": "localhost", "port": 1234,  "type": "http", "path": "/v1/models"},
    "bge_m3":      {"host": "localhost", "port": 8001,  "type": "http", "path": "/health"},
    "bce_reranker": {"host": "localhost", "port": 8002, "type": "http", "path": "/health"},
}

# Baseline documents to ingest
BASELINE_DOCS = [
    {"file": "simple_test.pdf",          "collection": "datasheet_chunks"},
    {"file": "stm32f407_datasheet.pdf",  "collection": "datasheet_chunks"},
]

# Baseline queries to generate traces
BASELINE_QUERIES = [
    "What are the GPIO specifications of STM32F407?",
    "What is the maximum clock speed of STM32F407?",
    "List the peripherals available on STM32F407",
]


# ── Helpers ──────────────────────────────────────────────────────────────

def check_port(host: str, port: int, timeout: float = 3.0) -> bool:
    """Check if a TCP port is reachable."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False


def check_http(host: str, port: int, path: str, timeout: float = 5.0) -> tuple[bool, str]:
    """Check if an HTTP endpoint is reachable. Returns (ok, body_preview)."""
    try:
        import httpx
        resp = httpx.get(f"http://{host}:{port}{path}", timeout=timeout)
        return resp.status_code == 200, resp.text[:200]
    except Exception:
        # Fallback to subprocess curl
        try:
            result = subprocess.run(
                ["curl", "-sf", "--max-time", str(int(timeout)),
                 f"http://{host}:{port}{path}"],
                capture_output=True, text=True,
            )
            return result.returncode == 0, result.stdout[:200]
        except FileNotFoundError:
            return False, "curl not found"


def run_cmd(args: list[str], check: bool = False, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess command from REPO_ROOT."""
    return subprocess.run(
        args, cwd=str(REPO_ROOT), check=check,
        capture_output=capture, text=True,
    )


def wait_for_service(name: str, info: dict, timeout: int = 60) -> bool:
    """Wait for a service to become healthy."""
    print(f"   Waiting for {name} (:{info['port']})...", end="", flush=True)
    start = time.time()
    while time.time() - start < timeout:
        if info["type"] == "tcp":
            ok = check_port(info["host"], info["port"])
        else:
            ok, _ = check_http(info["host"], info["port"], info.get("path", "/"))
        if ok:
            print(f" OK ({time.time() - start:.1f}s)")
            return True
        time.sleep(2)
    print(f" TIMEOUT ({timeout}s)")
    return False


# ── Commands ─────────────────────────────────────────────────────────────

def cmd_infra() -> bool:
    """Verify Docker containers healthy, run schema initialization."""
    print("🔧 Checking infrastructure...")

    # Start Docker Compose if not running
    result = run_cmd(["docker-compose", "ps", "--format", "json"])
    if result.returncode != 0 or not result.stdout.strip():
        print("   Starting Docker Compose...")
        run_cmd(["docker-compose", "up", "-d"])

    # Wait for core services
    infra_services = ["postgres", "milvus", "redis"]
    all_ok = True
    for svc in infra_services:
        if not wait_for_service(svc, SERVICES[svc], timeout=90):
            print(f"   ❌ {svc} failed to start")
            all_ok = False

    if not all_ok:
        print("❌ Infrastructure not fully healthy")
        return False

    # Run schema initialization (if scripts exist)
    init_scripts = [
        ("Alembic migration", [sys.executable, "-m", "alembic", "upgrade", "head"]),
        ("Milvus init", [sys.executable, str(REPO_ROOT / "scripts" / "init_milvus.py")]),
        ("Kùzu init", [sys.executable, str(REPO_ROOT / "scripts" / "init_kuzu.py")]),
    ]
    for label, cmd in init_scripts:
        script_path = cmd[-1] if cmd[0] == sys.executable and len(cmd) > 1 else None
        if script_path and not Path(script_path).exists() and "alembic" not in str(cmd):
            print(f"   ⏭️  {label} — script not found (Phase 1 task pending)")
            continue
        print(f"   Running {label}...")
        r = run_cmd(cmd)
        if r.returncode == 0:
            print(f"   ✅ {label}")
        else:
            print(f"   ⚠️  {label} — exit code {r.returncode}")
            if r.stderr:
                print(f"       {r.stderr[:150]}")

    print("✅ Infrastructure ready")
    return True


def cmd_models() -> bool:
    """Verify model services are responding."""
    print("🤖 Checking model services...")

    # Start model services Docker Compose if available
    services_compose = REPO_ROOT / "docker-compose.services.yml"
    if services_compose.exists():
        run_cmd(["docker-compose", "-f", str(services_compose), "up", "-d"])

    model_services = ["lm_studio", "bge_m3", "bce_reranker"]
    all_ok = True
    for svc in model_services:
        info = SERVICES[svc]
        ok, body = check_http(info["host"], info["port"], info.get("path", "/"))
        if ok:
            print(f"   ✅ {svc} (:{info['port']}) — {body[:80]}")
        else:
            print(f"   ❌ {svc} (:{info['port']}) — not responding")
            if svc == "lm_studio":
                print("       ℹ️  LM Studio must be started manually (not Docker-managed)")
            all_ok = False

    if all_ok:
        print("✅ All model services healthy")
    else:
        print("⚠️  Some model services unavailable")
    return all_ok


def cmd_baseline() -> bool:
    """Full setup: infra + models + seed documents + baseline queries."""
    print("📦 Setting up Baseline state...")
    print()

    # Step 1: Infrastructure
    if not cmd_infra():
        print("❌ Cannot set up baseline — infrastructure not ready")
        return False
    print()

    # Step 2: Models
    models_ok = cmd_models()
    if not models_ok:
        print("⚠️  Continuing baseline setup with degraded model services")
    print()

    # Step 3: Clear existing data
    cmd_clear()
    print()

    # Step 4: Ingest baseline documents
    print("📄 Ingesting baseline documents...")
    for doc in BASELINE_DOCS:
        filepath = FIXTURES_DIR / doc["file"]
        if not filepath.exists():
            print(f"   ⏭️  {doc['file']} — not found (will be created in later phase)")
            continue

        print(f"   → {doc['file']} → collection={doc['collection']}")

        # Try API upload first
        fastapi_ok, _ = check_http("localhost", 8080, "/health")
        if fastapi_ok:
            try:
                import httpx
                with open(filepath, "rb") as f:
                    resp = httpx.post(
                        "http://localhost:8080/api/v1/documents/upload",
                        files={"file": (doc["file"], f, "application/pdf")},
                        params={"collection": doc["collection"]},
                        timeout=120,
                    )
                if resp.status_code in (200, 202):
                    task_id = resp.json().get("task_id", "unknown")
                    print(f"   ✅ {doc['file']} (task_id={task_id})")
                else:
                    print(f"   ❌ {doc['file']} — HTTP {resp.status_code}")
            except Exception as e:
                print(f"   ❌ {doc['file']} — {e}")
        else:
            print(f"   ⏭️  FastAPI not running — cannot upload {doc['file']}")

    print()

    # Step 5: Run baseline queries to generate traces
    print("🔍 Running baseline queries...")
    fastapi_ok, _ = check_http("localhost", 8080, "/health")
    if fastapi_ok:
        for query in BASELINE_QUERIES:
            print(f"   → \"{query}\"")
            try:
                import httpx
                resp = httpx.post(
                    "http://localhost:8080/api/v1/query",
                    json={"query": query, "session_id": "qa-baseline"},
                    timeout=120,
                )
                if resp.status_code == 200:
                    print(f"   ✅ Done")
                else:
                    print(f"   ⚠️  HTTP {resp.status_code}")
            except Exception as e:
                print(f"   ⚠️  {e}")
    else:
        print("   ⏭️  FastAPI not running — skipping baseline queries")

    print()
    print("✅ Baseline setup complete")
    return True


def cmd_clear() -> None:
    """Clear all data → Empty state."""
    print("🗑️  Clearing all data...")

    # Clear PostgreSQL tables
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost", port=5432,
            dbname="chipwise", user="chipwise", password="chipwise",
        )
        conn.autocommit = True
        cur = conn.cursor()
        tables = ["chunks", "parameters", "errata", "documents", "chips"]
        for table in tables:
            try:
                cur.execute(f"TRUNCATE TABLE {table} CASCADE")
            except Exception:
                pass  # Table may not exist yet
        cur.close()
        conn.close()
        print("   ✅ PostgreSQL tables truncated")
    except ImportError:
        print("   ⏭️  psycopg2 not installed — skipping PG clear")
    except Exception as e:
        print(f"   ⚠️  PostgreSQL clear: {e}")

    # Flush Milvus collection
    try:
        from pymilvus import connections, utility, Collection
        connections.connect(host="localhost", port="19530")
        if utility.has_collection("datasheet_chunks"):
            col = Collection("datasheet_chunks")
            col.drop()
            print("   ✅ Milvus collection dropped")
        else:
            print("   ✅ Milvus — no collection to clear")
        connections.disconnect("default")
    except ImportError:
        print("   ⏭️  pymilvus not installed — skipping Milvus clear")
    except Exception as e:
        print(f"   ⚠️  Milvus clear: {e}")

    # Flush Redis
    try:
        import redis
        for db in [0, 1]:
            r = redis.Redis(host="localhost", port=6379, db=db)
            r.flushdb()
        print("   ✅ Redis flushed (DB0 + DB1)")
    except ImportError:
        print("   ⏭️  redis not installed — skipping Redis clear")
    except Exception as e:
        print(f"   ⚠️  Redis clear: {e}")

    # Clear Kùzu data directory
    kuzu_dir = DATA_DIR / "kuzu"
    if kuzu_dir.exists():
        import shutil
        shutil.rmtree(kuzu_dir)
        kuzu_dir.mkdir(parents=True)
        print("   ✅ Kùzu data directory cleared")
    else:
        print("   ✅ Kùzu — no data to clear")

    # Clear traces
    if TRACES_FILE.exists():
        TRACES_FILE.write_text("")
        print("   ✅ Traces cleared")

    print("✅ System is now in Empty state")


def cmd_status() -> None:
    """Show current system state."""
    print("📊 ChipWise Enterprise — System Status")
    print("=" * 55)

    # Service health
    print("\n🔌 Services:")
    for name, info in SERVICES.items():
        if info["type"] == "tcp":
            ok = check_port(info["host"], info["port"])
            status = "✅ UP" if ok else "❌ DOWN"
        else:
            ok, body = check_http(info["host"], info["port"], info.get("path", "/"))
            status = "✅ UP" if ok else "❌ DOWN"
        print(f"   {name:16s} :{info['port']:5d}  {status}")

    # PostgreSQL row counts
    print("\n📊 PostgreSQL:")
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost", port=5432,
            dbname="chipwise", user="chipwise", password="chipwise",
        )
        cur = conn.cursor()
        for table in ["chips", "parameters", "documents", "chunks", "errata"]:
            try:
                cur.execute(f"SELECT count(*) FROM {table}")
                count = cur.fetchone()[0]
                print(f"   {table:16s} {count} rows")
            except Exception:
                print(f"   {table:16s} (table not found)")
                conn.rollback()
        cur.close()
        conn.close()
    except ImportError:
        print("   (psycopg2 not installed)")
    except Exception as e:
        print(f"   (connection error: {e})")

    # Milvus entity counts
    print("\n🔍 Milvus:")
    try:
        from pymilvus import connections, utility, Collection
        connections.connect(host="localhost", port="19530")
        collections = utility.list_collections()
        if collections:
            for col_name in collections:
                col = Collection(col_name)
                col.load()
                print(f"   {col_name:24s} {col.num_entities} entities")
        else:
            print("   (no collections)")
        connections.disconnect("default")
    except ImportError:
        print("   (pymilvus not installed)")
    except Exception as e:
        print(f"   (connection error: {e})")

    # Redis key counts
    print("\n📦 Redis:")
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
        for pattern, label in [("session:*", "sessions"), ("gptcache:*", "cache"), ("ratelimit:*", "ratelimit")]:
            keys = r.keys(pattern)
            print(f"   {label:16s} {len(keys)} keys")
    except ImportError:
        print("   (redis not installed)")
    except Exception as e:
        print(f"   (connection error: {e})")

    # Kùzu node counts
    print("\n🕸️  Kùzu:")
    kuzu_dir = DATA_DIR / "kuzu"
    if kuzu_dir.exists() and any(kuzu_dir.iterdir()):
        try:
            import kuzu
            db = kuzu.Database(str(kuzu_dir))
            conn = kuzu.Connection(db)
            for table in ["Chip", "Parameter", "Errata", "Document", "DesignRule", "Peripheral"]:
                try:
                    result = conn.execute(f"MATCH (n:{table}) RETURN count(n) AS cnt")
                    if result.has_next():
                        print(f"   {table:16s} {result.get_next()[0]} nodes")
                except Exception:
                    print(f"   {table:16s} (not found)")
        except ImportError:
            print("   (kuzu not installed)")
        except Exception as e:
            print(f"   (error: {e})")
    else:
        print("   (empty — no data directory)")

    # Traces
    print("\n📝 Traces:")
    if TRACES_FILE.exists():
        lines = [l for l in TRACES_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
        print(f"   {len(lines)} entries in {TRACES_FILE.name}")
    else:
        print("   (no trace file)")


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="QA Bootstrap — manage ChipWise system state")
    parser.add_argument(
        "command",
        nargs="?",
        default="status",
        choices=["infra", "models", "baseline", "clear", "status"],
        help="Command to execute (default: status)",
    )
    args = parser.parse_args()

    commands = {
        "infra": cmd_infra,
        "models": cmd_models,
        "baseline": cmd_baseline,
        "clear": cmd_clear,
        "status": cmd_status,
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
