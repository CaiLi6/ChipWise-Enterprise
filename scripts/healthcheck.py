"""Unified infrastructure health check: PostgreSQL, Milvus, Redis, Kùzu.

Usage:
    python scripts/healthcheck.py                  # check all
    python scripts/healthcheck.py --service postgres  # single service
    python scripts/healthcheck.py --config path.yaml  # custom config

Exit codes: 0 = all healthy, 1 = at least one unhealthy.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# ── Data model ──────────────────────────────────────────────────────


@dataclass
class ServiceStatus:
    """Result of a single service health check."""

    name: str
    healthy: bool
    latency_ms: float
    message: str


# ── Timeout constant ────────────────────────────────────────────────

CONNECT_TIMEOUT_S = 5

# ── Individual checks ───────────────────────────────────────────────


def check_postgres(dsn: str) -> ServiceStatus:
    """Check PostgreSQL connectivity via ``SELECT 1``."""
    start = time.monotonic()
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(
            dsn,
            connect_args={"connect_timeout": CONNECT_TIMEOUT_S},
            pool_pre_ping=True,
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        elapsed = (time.monotonic() - start) * 1000
        return ServiceStatus(
            name="PostgreSQL", healthy=True, latency_ms=round(elapsed, 2), message="OK"
        )
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        return ServiceStatus(
            name="PostgreSQL",
            healthy=False,
            latency_ms=round(elapsed, 2),
            message=str(exc),
        )


def check_milvus(host: str, port: int) -> ServiceStatus:
    """Check Milvus connectivity and verify expected collections exist."""
    start = time.monotonic()
    try:
        from pymilvus import connections, utility

        connections.connect(
            alias="healthcheck", host=host, port=port, timeout=CONNECT_TIMEOUT_S
        )
        expected = ["datasheet_chunks", "knowledge_notes"]
        missing = [c for c in expected if not utility.has_collection(c, using="healthcheck")]
        connections.disconnect("healthcheck")
        elapsed = (time.monotonic() - start) * 1000

        if missing:
            return ServiceStatus(
                name="Milvus",
                healthy=False,
                latency_ms=round(elapsed, 2),
                message=f"Missing collections: {missing}",
            )
        return ServiceStatus(
            name="Milvus", healthy=True, latency_ms=round(elapsed, 2), message="OK"
        )
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        return ServiceStatus(
            name="Milvus",
            healthy=False,
            latency_ms=round(elapsed, 2),
            message=str(exc),
        )


def check_redis(url: str) -> ServiceStatus:
    """Check Redis connectivity via ``PING``."""
    start = time.monotonic()
    try:
        import redis as redis_lib

        client = redis_lib.Redis.from_url(
            url, socket_connect_timeout=CONNECT_TIMEOUT_S, socket_timeout=CONNECT_TIMEOUT_S
        )
        result = client.ping()
        client.close()
        elapsed = (time.monotonic() - start) * 1000
        if not result:
            return ServiceStatus(
                name="Redis",
                healthy=False,
                latency_ms=round(elapsed, 2),
                message="PING returned False",
            )
        return ServiceStatus(
            name="Redis", healthy=True, latency_ms=round(elapsed, 2), message="OK"
        )
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        return ServiceStatus(
            name="Redis",
            healthy=False,
            latency_ms=round(elapsed, 2),
            message=str(exc),
        )


def check_kuzu(db_path: str) -> ServiceStatus:
    """Check Kùzu database directory existence and execute a trivial query."""
    start = time.monotonic()
    try:
        path = Path(db_path)
        if not path.exists():
            elapsed = (time.monotonic() - start) * 1000
            return ServiceStatus(
                name="Kùzu",
                healthy=False,
                latency_ms=round(elapsed, 2),
                message=f"DB path does not exist: {db_path}",
            )

        import kuzu

        db = kuzu.Database(str(path))
        conn = kuzu.Connection(db)
        conn.execute("RETURN 1")
        elapsed = (time.monotonic() - start) * 1000
        return ServiceStatus(
            name="Kùzu", healthy=True, latency_ms=round(elapsed, 2), message="OK"
        )
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        return ServiceStatus(
            name="Kùzu",
            healthy=False,
            latency_ms=round(elapsed, 2),
            message=str(exc),
        )


# ── Aggregate check ─────────────────────────────────────────────────


def _build_dsn(db_settings) -> str:
    """Build a PostgreSQL DSN from DatabaseSettings."""
    return (
        f"postgresql://{db_settings.user}:{db_settings.password}"
        f"@{db_settings.host}:{db_settings.port}/{db_settings.database}"
    )


def _build_redis_url(redis_settings) -> str:
    """Build a Redis URL from RedisSettings."""
    if redis_settings.password:
        return f"redis://:{redis_settings.password}@{redis_settings.host}:{redis_settings.port}/{redis_settings.db}"
    return f"redis://{redis_settings.host}:{redis_settings.port}/{redis_settings.db}"


def check_all(settings) -> dict[str, ServiceStatus]:
    """Run all health checks and return a mapping of service name → status.

    Args:
        settings: A ``Settings`` instance (from ``src.core.settings``).

    Returns:
        dict mapping service name to its ``ServiceStatus``.
    """
    results: dict[str, ServiceStatus] = {}

    dsn = _build_dsn(settings.database)
    results["PostgreSQL"] = check_postgres(dsn)

    milvus = settings.vector_store.milvus
    results["Milvus"] = check_milvus(milvus.host, milvus.port)

    redis_url = _build_redis_url(settings.redis)
    results["Redis"] = check_redis(redis_url)

    kuzu_path = settings.graph_store.kuzu.db_path
    results["Kùzu"] = check_kuzu(kuzu_path)

    return results


# ── CLI ─────────────────────────────────────────────────────────────

_COLOR_GREEN = "\033[92m"
_COLOR_RED = "\033[91m"
_COLOR_RESET = "\033[0m"


def _print_results(results: dict[str, ServiceStatus]) -> None:
    """Pretty-print health check results."""
    print(f"\n{'Service':<15} {'Status':<10} {'Latency':<12} Message")
    print("-" * 60)
    for status in results.values():
        indicator = f"{_COLOR_GREEN}✓ OK{_COLOR_RESET}" if status.healthy else f"{_COLOR_RED}✗ FAIL{_COLOR_RESET}"
        print(f"{status.name:<15} {indicator:<22} {status.latency_ms:>8.1f} ms  {status.message}")
    print()


def main() -> int:
    """Entry point for CLI invocation. Returns 0 if all healthy, 1 otherwise."""
    import argparse

    parser = argparse.ArgumentParser(description="ChipWise infrastructure health check")
    parser.add_argument(
        "--config",
        default="config/settings.yaml",
        help="Path to settings.yaml (default: config/settings.yaml)",
    )
    parser.add_argument(
        "--service",
        choices=["postgres", "milvus", "redis", "kuzu"],
        help="Check a single service instead of all",
    )
    args = parser.parse_args()

    # Import here to avoid import errors when settings module isn't ready
    from src.core.settings import load_settings

    settings = load_settings(args.config)

    if args.service:
        dispatch: dict[str, Callable[[], ServiceStatus]] = {
            "postgres": lambda: check_postgres(_build_dsn(settings.database)),
            "milvus": lambda: check_milvus(
                settings.vector_store.milvus.host, settings.vector_store.milvus.port
            ),
            "redis": lambda: check_redis(_build_redis_url(settings.redis)),
            "kuzu": lambda: check_kuzu(settings.graph_store.kuzu.db_path),
        }
        result = dispatch[args.service]()
        results = {result.name: result}
    else:
        results = check_all(settings)

    _print_results(results)

    all_healthy = all(s.healthy for s in results.values())
    return 0 if all_healthy else 1


if __name__ == "__main__":
    sys.exit(main())
