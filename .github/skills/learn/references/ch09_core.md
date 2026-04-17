# Chapter 9: Core Libraries (核心基础库)

## Teaching Guide

### 1. Introduction

**Connect to all previous chapters**: "前面每一章都用到了 Settings、Types、TraceContext。今天我们看看这些'地基'是怎么建的。"

### 2. Key Concepts

#### Settings System (3 Layers)

```
config/settings.yaml          ← Base config (checked into git)
        ↓
Environment variables          ← Secrets override ($PG_PASSWORD, $JWT_SECRET_KEY)
        ↓
Pydantic validation            ← Type check + required field validation
        ↓
Settings singleton             ← Immutable, app-wide access
```

#### 5 Core Data Types

```
Document → Chunk → ChunkRecord → (search) → RetrievalResult
                                     ↑
                              ProcessedQuery
```

| Type | Role | Flows Through |
|------|------|---------------|
| `Document` | 入库文件元数据 | Ingestion pipeline |
| `Chunk` | 文本分片 + 位置信息 | Chunker → Embedder |
| `ChunkRecord` | Chunk + dense/sparse 向量 | Embedder → Milvus |
| `ProcessedQuery` | 改写后查询 + 上下文 + 实体 | Query rewriter → Agent |
| `RetrievalResult` | 排序后结果 + 引用来源 | Retrieval → ResponseBuilder |

#### TraceContext (请求追踪)

```python
trace = TraceContext(trace_id="req-123")
trace.record_stage("hybrid_search", {"count": 20, "latency_ms": 45})
trace.record_stage("rerank", {"top_k": 10, "latency_ms": 32})
# → logs/traces.jsonl
```

Every request gets a `trace_id` (from `X-Request-ID` header or auto-generated).

#### Resilience Patterns

- **Circuit Breaker**: failure_threshold=5 → open → recovery_timeout=30s → half-open → success_threshold=2 → closed
- **Retry (tenacity)**: per-service config in settings.yaml (LLM: 3 retries 2-15s, embedding: 4 retries 0.5-10s)
- **Rate Limit**: per-user (30/min, 500/hr) + global LLM semaphore (primary=2, router=10)

### 3. Code Walkthrough

**Files to read**:

1. `src/core/settings.py` — Full settings hierarchy + env overrides + validation
2. `src/core/types.py` — All 5 data types
3. `src/observability/trace_context.py` — TraceContext implementation

### 5. Quiz Questions

**Q1 (Concept)**: settings.yaml 中有 `${PG_PASSWORD}` 这样的占位符。它是怎么被替换的？和环境变量覆盖有什么区别？

**A1**: 两个独立机制：1) `_resolve_env_placeholders()` 替换 `${VAR}` 语法，适用于 YAML 中任何位置的字符串; 2) `_apply_env_overrides()` 根据 `_ENV_OVERRIDES` 映射表用环境变量覆盖特定字段路径。区别：占位符是"在 YAML 里显式写了要用环境变量"，覆盖是"不管 YAML 写了什么，环境变量优先"。

**Q2 (Code reading)**: `validate_settings()` 检查 `_REQUIRED_FIELDS` 列表。如果 `embedding.base_url` 为空字符串，验证会通过吗？

**A2**: 不会。代码用 `if not obj:` 检查，空字符串是 falsy，会触发 `ValueError("Missing required setting: embedding.base_url")`。

**Q3 (Design)**: 如果要给系统添加 Prometheus metrics 集成（比如记录每次检索的延迟），你会修改哪些文件？

**A3**: 1) 在 `src/observability/` 添加 metrics 模块; 2) 在 `src/api/main.py` 挂载 `/metrics` endpoint; 3) 在 `TraceContext.record_stage()` 中同时发射 Prometheus histogram; 4) requirements.txt 已有 `prometheus-client`，无需新增依赖。
