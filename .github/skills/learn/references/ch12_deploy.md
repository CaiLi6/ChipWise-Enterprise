# Chapter 12: Deployment & Operations (部署运维)

## Teaching Guide

### 1. Introduction

**Final chapter!** "前面 11 章讲了系统怎么构建。最后一章看怎么让它跑起来、跑得稳。"

### 2. Key Concepts

#### Service Map & Ports

```
┌─────────────────── Single Machine (128 GB RAM) ───────────────────┐
│                                                                   │
│  FastAPI :8080      ← 对外网关                                    │
│  LM Studio :1234    ← 35B + 1.7B 模型 (手动启动)                 │
│  BGE-M3 :8001       ← Embedding 微服务 (Docker)                  │
│  bce-reranker :8002 ← Reranker 微服务 (Docker)                   │
│  PostgreSQL :5432   ← 关系数据 (Docker, 4GB limit)               │
│  Milvus :19530      ← 向量数据 (Docker, 16GB limit)              │
│  Redis :6379        ← 缓存/队列 (Docker, 3GB limit)              │
│  Kuzu (embedded)    ← 图谱 (进程内, ~200MB)                      │
│  Gradio :7860       ← MVP UI (可选)                              │
│                                                                   │
│  Memory: PG 4G + Milvus 16G + Redis 3G + LM Studio ~40G         │
│         + BGE-M3 2.5G + Reranker 1G + App ~2G ≈ 70G             │
└───────────────────────────────────────────────────────────────────┘
```

#### Startup Order

```
1. docker-compose up -d              ← PG, Milvus, Redis
2. alembic upgrade head              ← DB schema
3. python scripts/init_milvus.py     ← Milvus collections
4. python scripts/init_kuzu.py       ← Graph schema
5. docker-compose -f docker-compose.services.yml up -d  ← BGE-M3, Reranker
6. (manual) LM Studio + load models
7. uvicorn src.api.main:app          ← FastAPI gateway
8. celery workers (3 workers + beat)
9. python scripts/healthcheck.py     ← Verify all green
```

#### Health Check Architecture

```
/health    → basic alive check
/readiness → full dependency check:
             PG: SELECT 1
             Redis: PING
             Milvus: has_collection
             LM Studio: /v1/models
             BGE-M3: /health
             Reranker: /health
             → "healthy" | "degraded" | "unhealthy"
```

#### Graceful Degradation Table

| Service Down | Impact | Fallback |
|-------------|--------|----------|
| LM Studio | No agent responses | 503 with Retry-After header |
| BGE-M3 | No embedding / search | PG ILIKE + ts_vector keyword search |
| bce-reranker | Less precise ranking | Use RRF raw scores |
| Milvus | No vector search | SQL-only search |
| Redis | No cache / sessions / queue | Direct query (slower), no rate limit |
| Kuzu | No graph boost | Skip graph boost step |

### 3. Code Walkthrough

**Files to read**:

1. `docker-compose.yml` — Infrastructure stack (PG, Milvus, Redis)
2. `docker-compose.services.yml` — Model microservices
3. `scripts/healthcheck.py` — Full health check script
4. `docs/DEPLOYMENT_CHECKLIST.md` — Step-by-step guide
5. `src/api/routers/health.py` — /readiness endpoint

### 5. Quiz Questions

**Q1 (Concept)**: 为什么 Milvus 分配 16GB 内存限制，而 PostgreSQL 只有 4GB？

**A1**: Milvus 需要将 HNSW 索引和向量数据加载到内存中（1024-dim × 数十万条 × 4 bytes = 几 GB）。sparse index 和 BM25 index 也占内存。PostgreSQL 的热数据相对小（芯片元数据是结构化的小行），4GB 足以覆盖 shared_buffers + work_mem。

**Q2 (Code reading)**: `/readiness` 返回 `degraded` 而不是 500，这对 Kubernetes 有什么意义？

**A2**: K8s readiness probe 根据状态码判断：200 = ready（接收流量），非 200 = not ready（摘除流量）。如果 `degraded` 返回 200，Pod 仍然接收请求（部分功能可用）。如果返回 503，Pod 被摘除（可能导致所有 Pod 都被摘除）。选择取决于业务策略——ChipWise 选择 degraded 仍可服务。

**Q3 (Design)**: 如果要把 ChipWise 从单机部署迁移到 3 节点集群，哪些组件最难迁移？为什么？

**A3**: 1) **Kuzu** 最难——嵌入式设计意味着只能单进程写入，多节点需要换成 Neo4j 或其他分布式图数据库; 2) **LM Studio** 较难——需要模型复制或负载均衡，GPU/CPU 资源分配复杂; 3) **Milvus** 最容易——本身支持分布式部署（data node / query node / index node 分离）; 4) **PG/Redis** 有成熟的主从方案。
