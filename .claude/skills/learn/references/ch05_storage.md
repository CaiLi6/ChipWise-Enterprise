# Chapter 5: Storage Layer (存储层)

## Teaching Guide

### 1. Introduction

**Connect to Chapter 4**: "上一章我们看到检索引擎从 Milvus 里搜向量、从 Kuzu 里查图谱。今天我们深入看看这 4 个数据库各自怎么工作。"

**Core analogy**: 想象一个图书馆——PostgreSQL 是图书目录卡片，Milvus 是"按内容相似度找书"的 AI 管理员，Redis 是前台的便签本（缓存），Kuzu 是书与书之间的引用关系图。

### 2. Key Concepts

#### 4 Databases, 4 Responsibilities

| Database | Stores | Why This One |
|----------|--------|-------------|
| PostgreSQL | 芯片元数据、用户、BOM、勘误 | ACID, 关系查询, Alembic 迁移 |
| Milvus | dense/sparse/BM25 向量 | 原生混合检索, 亿级扩展 |
| Redis | 缓存/会话/限流/队列 | 内存速度, TTL, PUB/SUB |
| Kuzu | 芯片-参数-替代-勘误图谱 | 嵌入式零运维, openCypher |

#### Factory Pattern (All 4 Share This)

```
src/libs/{component}/
  ├── base.py      ← Abstract base class
  ├── {impl}.py    ← Concrete implementation
  └── factory.py   ← Registry + create()
```

Switch backend by changing one YAML key. Zero code changes.

#### Milvus Collection Schema (12 fields + BM25 Function)

Key fields: chunk_id (PK), dense_vector (1024-dim HNSW), sparse_vector (BGE-M3 IP), bm25_vector (auto-generated from content), content, part_number, manufacturer...

#### Redis Key Namespaces (6 domains)

```
session:{user_id}:{session_id}  → conversation turns (TTL 1800s)
gptcache:*                      → semantic cache (TTL 3600-14400s)
ratelimit:{user_id}:*           → per-user limits
ratelimit:llm:semaphore         → global LLM concurrency
task:progress:{task_id}         → Celery progress (TTL 86400s)
DB 1                            → Celery broker (separate DB)
```

### 3. Code Walkthrough

**Files to read**:

1. `scripts/init_milvus.py` — Collection schema + BM25 Function + indexes
2. `src/libs/vector_store/milvus_store.py` — All Milvus operations
3. `src/libs/vector_store/factory.py` — Factory pattern reference
4. `scripts/init_kuzu.py` — Graph schema (6 nodes, 7 edges)
5. `src/libs/graph_store/kuzu_store.py` — Graph operations

**Key patterns**:
- Milvus BM25 Function auto-generates bm25_vector from content on insert
- Kuzu is embedded (no port, no Docker) — runs inside FastAPI process
- Redis DB 0 = cache + sessions, DB 1 = Celery broker (isolated)

### 4. Hands-on Verification

```bash
# Check Milvus schema definition
grep -n "FieldSchema" scripts/init_milvus.py

# See all Kuzu node/edge tables
grep -n "CREATE.*TABLE" scripts/init_kuzu.py
```

### 5. Quiz Questions

**Q1 (Concept)**: 为什么 Kuzu 选择嵌入式模式而不是像 Neo4j 那样独立部署？有什么权衡？

**A1**: 嵌入式的优势: 零运维（无端口、无容器）、低延迟（进程内调用）、低资源（mmap 读取）。权衡: 不能水平扩展、不支持多进程写入。对 ChipWise 的场景（芯片数据量不大、单机部署）完全够用。

**Q2 (Code reading)**: 在 `scripts/init_milvus.py` 中，`content` 字段添加了 `enable_analyzer=True`。这是给什么功能用的？如果不加会怎样？

**A2**: 给 Milvus BM25 Function 用的。BM25 需要对 content 进行分词（tokenization），`enable_analyzer=True` 启用 Milvus 内置分词器。不加的话，BM25 Function 无法正常工作，创建 schema 可能报错。

**Q3 (Design)**: 如果 Redis 完全挂了，ChipWise 还能工作吗？哪些功能会受影响？

**A3**: 核心查询能工作（走 Milvus + PG），但会退化：1) 语义缓存失效（每次查询都要走完整流程）; 2) 会话管理丢失（多轮对话断裂）; 3) 速率限制不生效; 4) Celery 队列不可用（新入库任务无法提交）; 5) SSO CSRF state 无法存储（登录流程中断）。这就是 CLAUDE.md 说的 "graceful degradation"。
