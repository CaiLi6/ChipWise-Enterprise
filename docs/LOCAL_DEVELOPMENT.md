# Local Development Guide

## Prerequisites

- Python 3.10+, Docker & Docker Compose, Git, Node.js 18+ (for Vue3 frontend)
- **No LM Studio required** — all LLM-dependent features are mocked or skipped locally

## Quick Start

```bash
# 1. Start Docker infrastructure
docker-compose up -d postgres redis milvus

# 2. (Optional) Local dev ports + Attu Web UI
cp docker-compose.override.yml.example docker-compose.override.yml
docker-compose up -d

# 3. Initialize schemas
alembic upgrade head
python scripts/init_milvus.py
python scripts/init_kuzu.py

# 4. Health check (local mode — skips LM Studio/Embedding/Reranker)
python scripts/healthcheck.py --local
```

## Running Tests Locally

```bash
# Unit tests (no Docker needed)
pytest -q -m unit

# Integration tests that DON'T need LM Studio
pytest -q -m integration_nollm

# Both together
pytest -q -m "unit or integration_nollm"

# Coverage report
pytest -q -m "unit or integration_nollm" --cov=src --cov-report=html
```

## What You CAN'T Run Locally

These require LM Studio or the full model service stack:

- `pytest -m integration` (full set — includes LM Studio-dependent tests)
- `pytest -m e2e` (full system end-to-end)
- Agent orchestrator real queries (`/api/v1/query`)
- Embedding service live tests (`:8001`)
- Reranker service live tests (`:8002`)

→ Push to GitHub, pull on the deployment machine (with LM Studio), run full tests there.

## Vue3 Frontend Development

```bash
cd frontend/web
npm install
npm run dev          # Dev server at http://localhost:5173
npm run build        # Production build
npm run preview      # Preview production build at http://localhost:4173
```

The frontend runs in mock mode when the backend isn't available — three core pages (Login, Query, Compare) show mock data.

## Environment Variables

Copy and edit `.env.example`:
```bash
cp .env.example .env
```

Key variables: `PG_PASSWORD`, `REDIS_PASSWORD`, `JWT_SECRET_KEY`, `SSO_CLIENT_SECRET`, `VITE_API_BASE_URL`.

## Workflow: Local → Deployment Machine

1. Develop & test locally (`pytest -m "unit or integration_nollm"`)
2. Lint: `ruff check src tests && mypy src`
3. Commit & push
4. On deployment machine: `git pull && pytest -q -m integration`
5. Start full stack with LM Studio for E2E verification
