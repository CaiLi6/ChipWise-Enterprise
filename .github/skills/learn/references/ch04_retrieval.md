# Chapter 4: Retrieval Engine (检索引擎)

## Teaching Guide

### 1. Introduction

**Connect to Chapter 3**: "上一章 Agent 选择了 rag_search 工具。今天我们看看这个工具内部是怎么找到最相关的文档片段的。"

**Core question**: 为什么单纯的向量搜索不够？为什么需要混合检索 + 重排序？

### 2. Key Concepts

#### Retrieval Pipeline

```
Query
  │
  ├─→ HybridSearch (dense + sparse/BM25, RRF fusion) → top_k*3 candidates
  │
  ├─→ CoreReranker (bce-reranker, score refinement)  → top_k results
  │
  └─→ GraphBoost (optional, Kuzu subgraph, ×1.15)   → final results
```

#### Two Sparse Methods (可切换)

```yaml
# config/settings.yaml
retrieval:
  sparse_method: bgem3  # or "bm25"
```

| | BGE-M3 Sparse | Milvus BM25 |
|---|---|---|
| 信号来源 | 模型学到的 token 权重 | 经典 TF-IDF/BM25 |
| 优势 | 语义理解更好 | 精确关键词匹配更强 |
| 适合 | "低功耗蓝牙芯片" | "STM32F407VGT6" |
| Milvus 字段 | sparse_vector (IP) | bm25_vector (BM25) |

#### Multi-Source Fusion

```
Vector (0.6) + SQL (0.2) + Graph (0.2) = Final Score
```

### 3. Code Walkthrough

**Files to read**:

1. `src/retrieval/hybrid_search.py` — Core: sparse_method routing, dense+sparse RRF
2. `src/retrieval/reranker.py` — CoreReranker with NoneReranker fallback
3. `src/retrieval/fusion.py` — MultiSourceFusion weighted scoring
4. `src/agent/tools/rag_search.py` — How the tool wires hybrid → rerank → graph boost

**Key patterns**:
- `_search_bm25()` vs `_search_bgem3()` — two code paths, one interface
- `return_sparse=False` in BM25 mode — skip unnecessary computation
- Fallback chain: hybrid fails → dense-only; reranker fails → RRF scores

### 4. Hands-on Verification

```bash
# Run hybrid search tests
pytest -q tests/unit/test_hybrid_search.py tests/unit/test_hybrid_search_bm25.py -v
```

### 5. Quiz Questions

**Q1 (Concept)**: RRF (Reciprocal Rank Fusion) 的公式是 `1/(k+rank)`。k=60 时，排名第 1 和第 10 的文档分数分别是多少？这个 k 值大小有什么影响？

**A1**: 第1名: 1/(60+1) = 0.0164, 第10名: 1/(60+10) = 0.0143。k 越大，不同排名之间的分数差异越小（更"平滑"），即更民主——不会过分偏向某一路的头部结果。k=60 是 Milvus 的推荐值。

**Q2 (Code reading)**: 在 `hybrid_search.py` 中，BM25 模式调用 `encode(return_sparse=False)`，为什么？如果改成 True 会怎样？

**A2**: BM25 模式不需要 BGE-M3 的 sparse 向量（Milvus 内部用原始文本做 BM25），所以 `return_sparse=False` 跳过 sparse 编码节省计算。改成 True 不会报错，只是浪费了一次 sparse 编码的计算（结果不会被使用）。

**Q3 (Design)**: 如果检索质量不好，你会按什么顺序排查？（提示：从数据到模型到参数）

**A3**: 1) **数据质量**: chunk 切分是否合理？表格提取是否正确？→ 检查 ingestion pipeline。2) **Embedding 质量**: BGE-M3 对专业术语的编码是否准确？→ 检查 embedding service。3) **检索参数**: top_k 是否足够？RRF k 值是否合适？→ 调 settings.yaml。4) **Reranker 效果**: bce-reranker 对中英文混合文本的排序是否准确？→ 对比有无 reranker 的结果。5) **sparse_method 选择**: 对精确型号搜索，BM25 可能比 BGE-M3 sparse 更好。
