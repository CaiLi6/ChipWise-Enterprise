# Chapter 6: Ingestion Pipeline (离线入库流水线)

## Teaching Guide

### 1. Introduction

**Connect to Chapter 5**: "上一章我们看了数据存在哪里。今天看看数据是怎么进去的——从一个 PDF 到向量库里的 chunk，中间经历了什么？"

**Core question**: 一份 200 页的芯片 Datasheet PDF，怎么变成可以被向量搜索的数据？

### 2. Key Concepts

#### Celery Chain (8 Steps)

```
Download → SHA256 Dedup → PDF Extract → 3-Tier Table Extract
    → LLM Param Extract → Chunk → Embed (BGE-M3) → Milvus Upsert
    → PG Upsert → Kuzu Graph Sync
```

#### 3 Worker Queues

| Worker | Queue | Why Separate |
|--------|-------|-------------|
| worker1 | default, embedding | 普通任务 + 向量化 |
| worker2 | heavy | PaddleOCR (3GB 内存, 按需加载) |
| worker3 | crawler | Playwright 爬虫 (域名限速) |

#### 5 Chunking Strategies

| Strategy | chunk_size | Use Case |
|----------|-----------|----------|
| datasheet | 1000 | Default for datasheets |
| fine | 256 | Precise parameter tables |
| coarse | 2048 | Overview sections |
| parent_child | 256/2048 | Hierarchical retrieval |
| semantic | 200-1500 | Content-aware boundaries |

#### 3-Tier PDF Table Extraction

```
Tier 1: pdfplumber (~70%, ~0.1s/page)
  ↓ (quality check failed)
Tier 2: Camelot (~20%, ~0.5s/page)
  ↓ (quality check failed)
Tier 3: PaddleOCR (~10%, ~3s/page, heavy queue)
```

### 3. Code Walkthrough

**Files to read**:

1. `src/ingestion/tasks.py` — Celery task chain definition
2. `src/ingestion/pdf_extractor.py` — 3-tier extraction logic
3. `src/ingestion/chunking/factory.py` — Chunking strategy selection
4. `src/ingestion/chunking/datasheet_splitter.py` — Default chunker
5. `src/ingestion/graph_sync.py` — PG → Kuzu synchronization
6. `src/ingestion/dedup.py` — SHA256 dedup check

**Key patterns**:
- `task_acks_late=True` — don't ACK until done (crash safety)
- `worker_prefetch_multiplier=1` — one task at a time (memory control)
- Exponential backoff: 2-60s, max 3 retries

### 4. Hands-on Verification

```bash
# See the Celery task definitions
grep -n "@app.task\|@shared_task" src/ingestion/tasks.py

# List all chunking strategies
ls src/ingestion/chunking/

# Check the factory registration
grep "register" src/ingestion/chunking/factory.py
```

### 5. Quiz Questions

**Q1 (Concept)**: 为什么 PaddleOCR 要放在单独的 heavy 队列？如果和其他任务共享 worker 会怎样？

**A1**: PaddleOCR 模型加载需要约 3GB 内存，推理时 CPU 占用很高。如果和其他任务共享 worker，一个 OCR 任务可能会把 worker 的内存和 CPU 耗尽，导致其他任务（如 embedding）被阻塞或 OOM。独立 worker 做到资源隔离。

**Q2 (Code reading)**: `task_acks_late=True` 和 `worker_prefetch_multiplier=1` 组合起来有什么作用？如果 worker 在处理任务中途 crash 了会怎样？

**A2**: `task_acks_late=True` 表示任务完成后才确认（ACK），crash 后消息还在 Redis 队列里。`prefetch_multiplier=1` 表示 worker 一次只取一个任务，不会预取多个。组合效果：crash 后未完成的任务会被其他 worker 重新执行，且不会丢失任何后续任务。这是 at-least-once delivery 保证。

**Q3 (Design)**: 如果 Datasheet 更新了（同一份 PDF 新版本），入库流程怎么处理？会不会产生重复数据？

**A3**: SHA256 dedup 是按文件哈希去重的。如果内容变了，SHA256 不同，会被当作新文件入库。旧版本的 chunks 不会自动删除。要实现"版本更新"，需要额外逻辑：按 doc_id 查找旧 chunks → 删除旧的 → 入库新的。这是一个可以改进的点。
