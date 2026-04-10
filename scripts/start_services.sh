#!/usr/bin/env bash
# ChipWise Enterprise — One-click service launcher
# Starts: Docker infra → LM Studio check → Embedding → Reranker
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[ChipWise]${NC} $*"; }
err()  { echo -e "${RED}[ChipWise ERROR]${NC} $*" >&2; }

wait_for_health() {
    local url=$1 max_wait=${2:-60} interval=${3:-3}
    local elapsed=0
    while [ $elapsed -lt $max_wait ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            return 0
        fi
        sleep "$interval"
        elapsed=$((elapsed + interval))
    done
    return 1
}

# ── Step 1: Docker infrastructure ───────────────────────────────────
log "Starting Docker infrastructure (PostgreSQL, Milvus, Redis) ..."
docker-compose up -d

log "Waiting for PostgreSQL ..."
if wait_for_health "localhost:5432" 30 2 2>/dev/null || \
   docker-compose exec -T postgres pg_isready -q 2>/dev/null; then
    log "✓ PostgreSQL ready"
else
    err "PostgreSQL did not become ready in time"
fi

log "Waiting for Redis ..."
if wait_for_health "localhost:6379" 15 2 2>/dev/null || \
   docker-compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
    log "✓ Redis ready"
else
    err "Redis did not become ready in time"
fi

log "Waiting for Milvus ..."
if wait_for_health "http://localhost:19530/v1/vector/collections" 60 3; then
    log "✓ Milvus ready"
else
    err "Milvus did not become ready in time (this can take 30-60s)"
fi

# ── Step 2: Check LM Studio ────────────────────────────────────────
log "Checking LM Studio at localhost:1234 ..."
if curl -sf http://localhost:1234/v1/models > /dev/null 2>&1; then
    log "✓ LM Studio is running"
else
    err "LM Studio is NOT running."
    err "Please start LM Studio manually and load the primary + router models."
    err "Then re-run this script or continue with model microservices."
fi

# ── Step 3: Model microservices ─────────────────────────────────────
log "Starting model microservices (Embedding :8001, Reranker :8002) ..."
docker-compose -f docker-compose.services.yml up -d

log "Waiting for Embedding Service ..."
if wait_for_health "http://localhost:8001/health" 180 5; then
    log "✓ Embedding Service ready"
else
    err "Embedding Service did not become ready (model loading may take 2-3 min)"
fi

log "Waiting for Reranker Service ..."
if wait_for_health "http://localhost:8002/health" 120 5; then
    log "✓ Reranker Service ready"
else
    err "Reranker Service did not become ready"
fi

# ── Summary ─────────────────────────────────────────────────────────
log ""
log "=== Service Status ==="
log "PostgreSQL  : localhost:5432"
log "Redis       : localhost:6379"
log "Milvus      : localhost:19530"
log "LM Studio   : localhost:1234"
log "Embedding   : localhost:8001"
log "Reranker    : localhost:8002"
log ""
log "Run 'python scripts/healthcheck.py' for detailed health check."
