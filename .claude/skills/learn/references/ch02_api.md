# Chapter 2: API Gateway (FastAPI 网关层)

## Teaching Guide

### 1. Introduction

**Connect to Chapter 1**: "上一章我们看到了 7 层架构，今天我们深入第 2 层——API Gateway。所有外部请求都要经过这一关。"

**Core question**: 一个 HTTP 请求从进入 FastAPI 到触发 Agent，中间经历了哪些处理？

### 2. Key Concepts

#### Router Architecture

```
src/api/main.py
    ├── /health, /readiness, /liveness  → health router
    ├── /api/v1/auth/*                  → auth router (local JWT)
    ├── /api/v1/auth/sso/*              → sso router (OIDC)
    ├── /api/v1/query                   → query router ★
    ├── /api/v1/compare                 → compare router
    ├── /api/v1/documents               → documents router
    ├── /api/v1/tasks                   → tasks router
    └── /api/v1/knowledge               → knowledge router
```

#### Middleware Chain (请求经过的层)

```
Request → CORS → RateLimit → TraceContext → JWT Auth → Router Handler → Response
```

#### Lazy Singleton Pattern (query router 的核心)

The `AgentOrchestrator` is created **lazily** on first request, not at startup. Why?
- LM Studio might not be running at startup
- If it fails, the app still starts and returns 503 gracefully
- Auto-heals: if LM Studio recovers, next request recreates the orchestrator

### 3. Code Walkthrough

**Files to read**:

1. `src/api/main.py` — Router registration, middleware setup, lifespan
2. `src/api/routers/query.py` — The most important router: lazy orchestrator + query endpoint
3. `src/api/dependencies.py` — DI container: settings, DB pool, Redis, HTTP clients
4. `src/api/routers/health.py` — Simple health check pattern

**Key patterns to highlight**:
- `_get_or_create_orchestrator()` — lazy init with auto-heal
- `Depends(get_settings)` — singleton settings injection
- `Depends(get_current_user)` — JWT auth as dependency
- `app.dependency_overrides` — how tests bypass real auth

### 4. Hands-on Verification

```bash
# Check all registered routers
grep -n "app.include_router" src/api/main.py

# See the query endpoint signature
grep -A 10 "async def query" src/api/routers/query.py
```

### 5. Quiz Questions

**Q1 (Concept)**: `/readiness` 和 `/liveness` 有什么区别？为什么 Kubernetes 需要两个不同的探针？

**A1**: `/liveness` 检查进程是否存活（不存活就重启 Pod），`/readiness` 检查服务是否能处理请求（不就绪就从负载均衡摘除）。ChipWise 的 `/readiness` 在 Milvus/Redis 不可用时返回 `degraded` 而非 500——进程活着但不能完全服务。

**Q2 (Code reading)**: 在 `src/api/routers/query.py` 中，如果 `orchestrator is None` 但 LM Studio 的 health check 返回 healthy，会发生什么？

**A2**: 代码会重置 `_orchestrator_initialized = False`，然后调用 `_get_or_create_orchestrator()` 重新创建。这是自动愈合机制——LM Studio 恢复后，下一个请求就能正常使用 Agent。

**Q3 (Design)**: 如果要给 ChipWise 添加一个 WebSocket 实时通知功能（比如入库进度推送），你会放在哪个 router 里？需要修改 dependencies.py 吗？

**A3**: 放在 `tasks` router（已有 WebSocket push 的设计）。需要在 `dependencies.py` 确保 Redis client 可用（用于 PUB/SUB 推送进度）。不需要新建 router，因为任务进度推送属于 tasks 的职责范围。
