# Chapter 7: Model Services (模型服务层)

## Teaching Guide

### 1. Introduction

**Connect to Chapter 6**: "入库流水线的第 7 步是 BGE-M3 向量化。今天我们看看所有模型服务——LLM、Embedding、Reranker——是怎么组织和管理的。"

### 2. Key Concepts

#### 3 Model Services

| Service | Port | Model | Role |
|---------|------|-------|------|
| LM Studio | 1234 | qwen3-35b (primary) | 推理、生成答案 |
| LM Studio | 1234 | qwen3-1.7b (router) | 意图分类、工具选择 |
| BGE-M3 FastAPI | 8001 | BAAI/bge-m3 | Dense+Sparse embedding |
| bce-reranker FastAPI | 8002 | bce-reranker-base_v1 | 精排序 |

#### Factory + Registry Pattern

每个模型服务都有相同的三文件结构:
```
base.py     → ABC (encode/generate/rerank)
{impl}.py   → HTTP client implementation
factory.py  → Registry: name → class mapping
```

`LLMFactory.create(config, role="primary")` → 35B model
`LLMFactory.create(config, role="router")` → 1.7B model

#### EmbeddingResult 数据结构

```python
@dataclass
class EmbeddingResult:
    dense: list[list[float]]        # 1024-dim vectors
    sparse: list[dict[int, float]]  # token_id → weight
    dimensions: int
```

One BGE-M3 call produces both dense and sparse — no separate indexing pipeline needed.

#### Prompt Management

All LLM prompts live in `config/prompts/*.txt`. Never hardcoded in Python. This enables:
- Non-developer prompt tuning
- Version control on prompts
- A/B testing different prompts

### 3. Code Walkthrough

**Files to read**:

1. `src/libs/llm/base.py` — BaseLLM ABC
2. `src/libs/llm/lmstudio_client.py` — OpenAI-compatible HTTP client
3. `src/libs/llm/factory.py` — LLMFactory with primary/router role
4. `src/libs/embedding/bgem3_client.py` — BGE-M3 HTTP client (dense + sparse)
5. `src/libs/reranker/factory.py` — Reranker factory with "none" fallback

### 5. Quiz Questions

**Q1 (Concept)**: 为什么需要 primary (35B) 和 router (1.7B) 两个模型？单用 35B 不行吗？

**A1**: 35B 推理慢且并发受限（max_concurrent=2）。router 用 1.7B 做轻量决策（意图分类、工具选择），速度快 10x 且并发高（max_concurrent=10）。只用 35B 会导致：简单的路由判断占用大模型资源，系统吞吐量降低。

**Q2 (Code reading)**: BGE-M3 client 有 `return_sparse` 参数。在哪些场景下它是 False？

**A2**: 在 `HybridSearch._search_bm25()` 中，`encode(return_sparse=False)`。因为 BM25 模式不需要 BGE-M3 的 sparse 向量（Milvus 内部用原文做 BM25），跳过 sparse 编码节省计算。其他场景（BGE-M3 sparse 模式、入库时）都是 True。

**Q3 (Design)**: CLAUDE.md 提到未来可能迁移到 Jina v3 Embedding。Factory 抽象如何让这个迁移变简单？

**A3**: 只需：1) 创建 `src/libs/embedding/jina_client.py` 实现 `BaseEmbedding`; 2) 在 factory 注册 `"jina"` → `JinaClient`; 3) settings.yaml 改 `embedding.provider: jina`。零代码改动——HybridSearch 等调用方只依赖 `BaseEmbedding` 接口，不关心具体实现。
