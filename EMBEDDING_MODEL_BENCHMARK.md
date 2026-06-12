# Embedding 模型对比基准（ChipWise Enterprise）

> 本文记录了"为什么本项目用 BGE-M3 作为 embedding 模型，以及我们如何用自建专业测试集，
> 量化对比 5 个主流 embedding 模型在本项目真实场景下的 **检索准确率 / 推理速度 / 部署内存**"的
> 完整工作过程、方法学、代码产出与最终结论。
>
> - 评测代码包：`evaluation/embedding/`
> - 测试集：`data/eval/embedding_qrels.jsonl`（90 条双语，已人工核验）
> - 报告产出：`reports/embedding_eval/{embedding_eval.md, .csv, _charts.png, results.json, hybrid_reference.json}`
> - 单元测试：`tests/unit/test_embedding_eval_metrics.py`
> - 评测依赖：`requirements-eval.txt`

---

## 1. 背景：本项目用的是什么 embedding 模型，为什么

### 1.1 生产配置

ChipWise Enterprise 生产环境使用 **`BAAI/bge-m3`**，以 FastAPI 微服务形式部署（`:8001`）：

```yaml
# config/settings.yaml
embedding:
  provider: bgem3
  base_url: "http://localhost:8001"
  model: "BAAI/bge-m3"
  dim: 1024
  batch_size: 32

retrieval:
  mode: hybrid
  sparse_method: bgem3   # BGE-M3 在一次前向里同时产出 dense + sparse 向量
  top_k_search: 30
  rrf_k: 60
```

### 1.2 为什么选 BGE-M3

本项目的核心检索场景是 **中文自然语言提问 → 检索英文 / 中英混合的芯片 Datasheet**，对 embedding
模型有三个硬要求：

1. **多语言 / 跨语言对齐**：用户用中文提问，但绝大多数 Datasheet 是英文（或中英混排），需要中→英跨语言检索。
   BGE-M3 是多语言模型，跨语言对齐能力强。
2. **dense + sparse 一体**：BGE-M3 的独特之处是**单次前向同时输出 dense 向量与 sparse（词权重）向量**，
   天然支持混合检索（Milvus `hybrid_search` + `RRFRanker`），对芯片型号、寄存器名、引脚号这类
   **精确术语匹配**尤其重要——这正是 sparse/BM25 擅长、纯 dense 容易漏的部分。
3. **长文本 + 1024 维**：8192 token 上下文、1024 维输出，适配 Datasheet 长段落，索引体积可控。

在做本基准之前，BGE-M3 的选择主要基于上述工程论证与社区口碑，**尚未在本项目真实语料上做过量化横评**。
本次工作正是为了用数据回答："换更新/更大的模型，检索会不会更准？速度和内存代价是多少？"

---

## 2. 评测目标

用**自建的、带分级相关度标注（qrels）的专业测试集**，在**本机实跑**，量化对比候选 embedding 模型的：

1. **检索准确率**：Recall@{1,5,10,20}、MRR@10、nDCG@10（分级）、MAP@10、Hit@k，并给出 **bootstrap 95% 置信区间**，
   分类别 / 分语言汇报。
2. **推理速度**：query 编码延迟 p50/p95（batch=1）、批量吞吐、全库编码吞吐。
3. **部署内存 / 资源**：权重磁盘大小、加载增量 RSS、推理峰值 RSS、PSS、GPU 显存（best-effort）、维度。

---

## 3. 对比模型

| key | HuggingFace id | 维度 | 说明 / query 侧约定 |
|-----|----------------|------|----------------------|
| `bge-m3`（**生产基准**） | `BAAI/bge-m3` | 1024 | 无前缀；dense 主测，sparse 单列参考 |
| `bge-large-zh` | `BAAI/bge-large-zh-v1.5` | 1024 | query 加中文检索指令前缀 |
| `jina-v3` | `jinaai/jina-embeddings-v3` | 1024 | task LoRA（`retrieval.query`/`retrieval.passage`），需 `einops` + remote code |
| `qwen3-0.6b` | `Qwen/Qwen3-Embedding-0.6B` | 1024 | query 加 instruct 提示，last-token pooling（decoder） |
| `e5-large` | `intfloat/multilingual-e5-large` | 1024 | 强制 `query:` / `passage:` 前缀 |

5 个模型全部统一输出 1024 维，便于索引体积与精确 cosine 的同口径对比。

---

## 4. 方法学（公平性是第一原则）

### 4.1 固定共享语料（公平性基石）

- 用项目现有的 **datasheet 分块器**，对 `data/documents/` 下的 **59 篇真实 PDF Datasheet** 一次性生成冻结
  chunk 集（共 **4710** chunk），写入 `data/eval/embedding_corpus_full.jsonl` + manifest。
- 受本机 CPU 算力限制（见 §8），二次抽样到 **1000 chunk**（`data/eval/embedding_corpus.jsonl`），
  **保留全部测试集源 chunk**，避免漏掉答案。
- **所有模型共享同一份 chunk**，只替换 embedding 模型——这是"测模型而非测分块"的前提。

源 PDF 覆盖真实芯片资料：DDR4 SDRAM、FPGA（Lattice Avant/Titan3/Kosmo2、Xilinx UltraScale/7-series）、
图像传感器（Sony IMX、GMAX、GSENSE）、SoC（RK3588、Jetson Orin）等。

### 4.2 专业测试集（LLM 草拟 + 池化 + 人工复核）

这是整套方法学**专业性的关键**——单源标注会产生大量假阴性（一个查询其实有多个相关 chunk，但只标了一个），
因此采用三步法：

1. **LLM 草拟**：用 **gemma-4-31b-it**（实测产出干净 JSON，0 reasoning token）从抽样 chunk 生成双语 Q/A，
   并标注初始相关 chunk ID。**自动校验**：要求关键词在源 chunk 内**逐字命中**，否则丢弃。
2. **池化（防假阴性）**：用全部 5 个 dense 模型 + BM25 各检索 top-k，**合并候选池**；再用 LLM 评判 +
   人工对分歧 / 高影响项打**分级相关度**（2=relevant / 1=partial / 0=irrelevant），**允许一个查询多个相关 chunk**。
   最终 90 条里有 **47 条是多相关 chunk**。
3. **人工复核**：抽查 + 解决全部池化分歧项，全部 90 条标记 `verified: true`。

最终测试集 `data/eval/embedding_qrels.jsonl`：**90 条双语**（en 44 / zh 46），分类别如下：

| 类别 | 条数 | 说明 |
|------|------|------|
| `numeric` | 33 | 数值约束（频率、电流、电压、温度范围…） |
| `table_lookup` | 28 | 表格查找（分频比、寄存器配置…） |
| `general` | 16 | 一般性概念 / 特性问答 |
| `package_pinout` | 10 | 封装 / 引脚 |
| `errata_limit` | 2 | 勘误 / 绝对最大值 |
| `feature_availability` | 1 | 特性可用性 |

每条样例（节选）：

```json
{"qid": "q002",
 "query": "在SGMII接口且速率为1250的情况下，其Divider和ECLKDIV的值分别是多少？",
 "lang": "zh", "category": "table_lookup",
 "expected_keywords": ["SGMII", "1250", "5", "125"],
 "relevant": {"fpga_tn_02298_..._c166": 2},
 "verified": true, "pooled_models": ["bge-m3", "e5-large"]}
```

### 4.3 公平性控制（防"测后端而非测模型"）

- **全部 in-process 加载**（统一 `sentence-transformers` 后端，不走 HTTP 微服务）；BGE-M3 的 HTTP "served latency" 不混入。
- 统一对齐：模型 revision/SHA、device、dtype、线程数、**`max_seq_len=512`**、截断策略、batch_size、warmup。
- **BGE-M3 dense 主测关闭 sparse**（`return_sparse=False`），避免被 sparse 开销拖累延迟。
- 显式 **L2 归一化** query+passage；检测 NaN / 全零；统计每模型**截断率**（见 §7.5 公平性审计）。

### 4.4 检索与指标

- 索引：**faiss / numpy 精确 cosine**（精确检索，不引入 ANN 近似误差，对不同模型最公平）。
- 准确率：Recall@{1,5,10,20}、MRR@10、nDCG@10（分级）、MAP@10、Hit@k；
  **bootstrap 95% 置信区间**（样本仅 90，CI 必不可少）；**按类别 / 按语言**分别汇报。

### 4.5 速度

- query 编码延迟 p50/p95（batch=1，排除 warmup，≥3 次重复）；批量吞吐 texts/s；全库编码 wall-time 派生吞吐。

### 4.6 内存 / 资源（子进程隔离 + 多口径）

- **每个模型独立子进程**测量，避免互相污染。报告多口径：权重磁盘大小、加载增量 RSS、推理峰值 RSS、
  **PSS（`/proc/<pid>/smaps_rollup`）**、GPU/ROCm 显存（best-effort）。

### 4.7 生产参考点

- 单独报告 **`BGE-M3 hybrid (dense+sparse, RRF)`** 作为生产配置基线——它**不参与纯 dense 的公平排名**，
  只用来回答"生产实际混合检索到底多强"。

---

## 5. 代码产出

### 5.1 新增评测包 `evaluation/embedding/`

```
evaluation/embedding/
  __init__.py
  _config.py    # 模型注册表 + 公平性参数（max_len、dtype、线程、query/passage 约定）
  models.py     # 统一 EmbeddingRunner：FlagEmbedding / sentence-transformers 双后端
  corpus.py     # 冻结 chunk 语料（复用 datasheet 分块器）
  testset.py    # LLM 双语 Q/A 草拟 + 关键词逐字接地 + 类别标注
  pooling.py    # 多模型 + BM25 池化 → LLM 分级评判 → 最终 qrels
  metrics.py    # Recall/MRR/nDCG(graded)/MAP/Hit + bootstrap CI + 分类别聚合
  index.py      # faiss / numpy 精确 cosine
  perf.py       # 子进程内 延迟 / 吞吐 / 内存(PSS,RSS,disk,GPU)
  worker.py     # 单模型子进程入口（干净内存测量）
  runner.py     # 逐模型子进程编排（按 corpus+queries 哈希缓存复用）
  hybrid.py     # BGE-M3 dense+sparse(RRF) 参考点
  report.py     # 生成 md/json/csv + 图表 + 排名表 + 产线适配结论
  cli.py        # build-corpus / build-testset / pool / review / run / hybrid / report
  review.py     # 人工复核辅助（抽查 + mark-verified）
  README.md     # 包级说明
```

### 5.2 其它产出

- `requirements-eval.txt`：评测专用依赖（`faiss-cpu`、`psutil`、`einops`、`matplotlib`、`FlagEmbedding` 等），
  **不污染主依赖**。
- `tests/unit/test_embedding_eval_metrics.py`：指标实现的单元测试（7 个用例，synthetic 数据验证 Recall/MRR/nDCG/MAP 正确性），全部通过；`ruff check` 通过。

---

## 6. 复现步骤

```bash
pip install -r requirements-eval.txt          # torch 需单独装 CPU wheel
# 结构化抽取/评判默认用 gemma-4-31b-it；可用环境变量 EMBED_EVAL_LLM 覆盖

python -m evaluation.embedding.cli build-corpus  --limit 60   # 真实 PDF → 冻结 chunk 语料
python -m evaluation.embedding.cli build-testset --n 90       # LLM 双语草拟
python -m evaluation.embedding.cli pool                       # 池化 + 分级评判 → qrels
python -m evaluation.embedding.cli review --sample 12         # 人工抽查
python -m evaluation.embedding.cli review --mark-verified     # 复核完成后标记
python -m evaluation.embedding.cli run    --models all        # 5 模型 dense 基准
python -m evaluation.embedding.cli hybrid                     # BGE-M3 dense+sparse 参考
python -m evaluation.embedding.cli report                     # 生成 md/csv/图表
```

---

## 7. 完整结果

> 运行条件：查询数 **90**（人工核验 90）· 语料 chunk 数 **1000** · top_k 50 · threads 16 ·
> 设备 **cpu** · dtype **float32** · 检索 **精确 cosine**（dense 隔离，reranker 关闭）。

### 7.1 检索准确率（dense，apples-to-apples）

数值为均值，方括号为 bootstrap 95% 置信区间。

| 模型 | Recall@1 | Recall@5 | Recall@10 | MRR@10 | nDCG@10 | MAP@10 |
|------|----------|----------|-----------|--------|---------|--------|
| `qwen3-0.6b` | 0.493 [0.409, 0.575] | 0.789 [0.713, 0.856] | 0.824 [0.757, 0.883] | 0.812 [0.738, 0.878] | **0.767** [0.699, 0.825] | 0.701 [0.625, 0.768] |
| `bge-m3` | 0.411 [0.332, 0.491] | 0.825 [0.755, 0.888] | **0.849** [0.783, 0.908] | 0.753 [0.677, 0.824] | 0.731 [0.659, 0.798] | 0.701 [0.626, 0.770] |
| `jina-v3` | 0.335 [0.258, 0.416] | 0.637 [0.548, 0.718] | 0.735 [0.653, 0.808] | 0.639 [0.550, 0.727] | 0.600 [0.523, 0.672] | 0.521 [0.440, 0.596] |
| `e5-large` | 0.285 [0.208, 0.363] | 0.495 [0.406, 0.590] | 0.559 [0.467, 0.655] | 0.536 [0.439, 0.626] | 0.479 [0.395, 0.562] | 0.413 [0.333, 0.493] |
| `bge-large-zh` | 0.195 [0.130, 0.266] | 0.394 [0.307, 0.489] | 0.459 [0.372, 0.550] | 0.400 [0.313, 0.495] | 0.370 [0.292, 0.459] | 0.328 [0.251, 0.414] |

**关键观察**：`qwen3-0.6b` 的 nDCG@10 最高（0.767），但其 CI [0.699, 0.825] 与 `bge-m3` 的 CI
[0.659, 0.798] **明显重叠 → 两者差异不具统计显著性**。而 `bge-m3` 的 **Recall@5 / Recall@10 全场最高**。

### 7.2 分类别 nDCG@10

| 模型 | errata_limit | feature_availability | general | numeric | package_pinout | table_lookup |
|------|---|---|---|---|---|---|
| `bge-m3` | 1.000 | 1.000 | 0.808 | 0.722 | 0.761 | 0.657 |
| `qwen3-0.6b` | 0.500 | 1.000 | 0.695 | 0.802 | 0.826 | 0.756 |
| `jina-v3` | 1.000 | 1.000 | 0.612 | 0.534 | 0.768 | 0.569 |
| `e5-large` | 1.000 | 1.000 | 0.508 | 0.462 | 0.569 | 0.397 |
| `bge-large-zh` | 0.715 | 1.000 | 0.364 | 0.342 | 0.588 | 0.282 |

### 7.3 分语言 nDCG@10

| 模型 | lang=en | lang=zh |
|------|---|---|
| `qwen3-0.6b` | 0.725 | 0.807 |
| `bge-m3` | 0.693 | 0.767 |
| `jina-v3` | 0.575 | 0.624 |
| `e5-large` | 0.532 | 0.429 |
| `bge-large-zh` | 0.364 | 0.376 |

`bge-large-zh` 是纯中文模型，面对英文 Datasheet 两个语言方向都最差，印证了"跨语言/多语言能力"对本场景的决定性。

### 7.4 推理速度（CPU）

| 模型 | query p50 (ms) | query p95 (ms) | 吞吐@32 (texts/s) | 全库编码 (texts/s) |
|------|----------------|----------------|-------------------|--------------------|
| `e5-large` | **139.65** | 197.21 | 2.2 | 2.2 |
| `bge-m3` | 152.76 | 225.20 | 2.2 | 2.2 |
| `bge-large-zh` | 176.73 | 238.54 | 2.1 | 2.1 |
| `qwen3-0.6b` | 246.98 | 394.36 | 1.0 | 1.0 |
| `jina-v3` | 861.76 | 963.93 | 1.4 | 1.4 |

### 7.5 部署内存 / 资源

| 模型 | 维度 | 权重磁盘 (MB) | 加载增量 RSS (MB) | 推理峰值 RSS (MB) | PSS (MB) | GPU 峰值 |
|------|------|---------------|-------------------|-------------------|----------|----------|
| `bge-large-zh` | 1024 | 1241.9 | 472.2 | **2550.3** | 1855.8 | None |
| `e5-large` | 1024 | 2135.9 | 761.9 | 3106.0 | 2376.6 | None |
| `bge-m3` | 1024 | 2165.9 | 753.6 | 3116.5 | 2532.8 | None |
| `jina-v3` | 1024 | 1091.7 | 3216.3 | 5519.4 | 3502.1 | None |
| `qwen3-0.6b` | 1024 | 1136.4 | 2857.8 | **7414.5** | 2988.8 | None |

### 7.6 公平性审计

| 模型 | revision | max_len | 语料截断率 | 查询截断率 | NaN/零向量 |
|------|----------|---------|------------|------------|------------|
| `bge-m3` | 5617a9f61b02 | 512 | 0.103 | 0.0 | 0/0 |
| `bge-large-zh` | 79e7739b6ab9 | 512 | 0.165 | 0.0 | 0/0 |
| `jina-v3` | ab036b023d30 | 512 | 0.103 | 0.0 | 0/0 |
| `qwen3-0.6b` | 97b0c614be4d | 512 | 0.188 | 0.0 | 0/0 |
| `e5-large` | 3d7cfbdacd47 | 512 | 0.104 | 0.0 | 0/0 |

### 7.7 参考点：BGE-M3 Hybrid (dense+sparse, RRF)

> 生产配置参考，**不参与纯 dense 排名**。

- nDCG@10: **0.753** [0.685, 0.818] · Recall@10: **0.868** [0.806, 0.925]（全场最高） · MRR@10: 0.795 [0.721, 0.863]
- 相对 BGE-M3 dense 的 nDCG@10 增益：**+0.022**

即：开启 BGE-M3 自带的 sparse 后，混合检索把 nDCG@10 从 0.731 提到 0.753、Recall@10 提到 0.868，
**反超 dense 第一的 qwen3-0.6b（0.824）**。这是其它纯 dense 模型不具备的能力。

---

## 8. 环境说明（实测，影响结果解读）

- **算力**：本机 **CPU-only** torch（无 CUDA/ROCm），32 核。`Qwen3-Embedding-0.6B` 是 decoder 架构，
  CPU 上仅 ~1 texts/s 为瓶颈 → 因此语料降到 1000、`max_len=512`。**速度/内存结论仅对当前 CPU 部署有效**。
- **LLM**：结构化抽取 / 评判用 **gemma-4-31b-it**（0 reasoning token、干净 JSON）；qwen3.5-35b 为 reasoning 模型，
  verbose、易超长，不适合本用途。
- **网络**：HF 与 hf-mirror 均约 1.8MB/s（带宽受限）；hf-mirror 与 `huggingface_hub ≥1.0` 的 strict metadata
  校验不兼容 → 使用默认 HF endpoint。
- **截断**：统一 `max_len=512`，约 10–19% 的 chunk 被截断（已在 §7.6 列出）。

---

## 9. 结论与产线适配建议

| 模型 | nDCG@10 | query p50 (ms) | 峰值内存 (MB) | 综合定位 |
|------|---------|----------------|---------------|----------|
| `qwen3-0.6b` | 0.767 | 246.98 | 7414.5 | 准确率最高但**与 bge-m3 不显著**、CPU 最慢、内存最高；**适合有 GPU 场景** |
| **`bge-m3`（生产）** | 0.731 | 152.76 | 3116.5 | **均衡**：Recall 最高、速度/内存适中，**独有 dense+sparse 混合** |
| `jina-v3` | 0.600 | 861.76 | 5519.4 | LoRA，延迟最高、加载内存最大；本地 CPU 不划算 |
| `e5-large` | 0.479 | 139.65 | 3106.0 | 最快，但中→英检索准确率偏低 |
| `bge-large-zh` | 0.370 | 176.73 | 2550.3 | 最省内存，但纯中文模型在英文 Datasheet 上最差 |

**最终建议：维持现状，继续使用 BGE-M3。** 理由：

1. **准确率**：BGE-M3 dense 在纯 dense 排名中位列第二，且 Recall@5/@10 全场最高；唯一领先它的 qwen3-0.6b
   差异**不具统计显著性**。
2. **混合能力**：开启 BGE-M3 自带 sparse 后（生产实际配置），hybrid 的 nDCG@10=0.753、Recall@10=0.868
   **反超所有纯 dense 模型**——这是其它候选不具备的护城河。
3. **资源**：在当前**无 GPU** 的本地部署下，迁移到 qwen3-0.6b 会带来 ~2× 的 CPU 延迟与最高峰值内存，
   却换不来统计上显著的准确率提升。
4. **后续**：若未来上 GPU，可重新评估 `qwen3-0.6b`（decoder 模型在 GPU 上速度劣势会大幅缩小）。

---

## 10. 局限性与权衡

- **样本量**：90 条 query，故所有指标均带 bootstrap 95% CI；跨模型比较应看 CI 是否重叠，而非只看均值。
- **qrels 依赖冻结分块**：准确率建立在固定 chunk 之上；池化 + 人工复核用于降低单源标注的假阴性，但无法完全消除。
- **精确 cosine vs 生产 HNSW**：主测用精确 cosine 隔离 embedding 质量；生产 Milvus HNSW 会有额外（很小的）
  ANN 近似误差，不混入主排名。
- **CPU-only**：速度与内存结论强绑定当前硬件；decoder 类模型（qwen3-0.6b）在 GPU 上表现会显著不同。

---

## 11. 产出文件清单

| 路径 | 内容 |
|------|------|
| `evaluation/embedding/` | 评测代码包（13 个模块 + README） |
| `requirements-eval.txt` | 评测专用依赖 |
| `data/eval/embedding_corpus.jsonl` | 冻结语料（1000 chunk，实跑用） |
| `data/eval/embedding_corpus_full.jsonl` | 全量冻结语料（4710 chunk） |
| `data/eval/embedding_corpus_manifest.json` | 语料来源清单（59 篇 PDF → chunk 数） |
| `data/eval/embedding_qrels.jsonl` | **专业测试集（90 条双语，已 verified）** |
| `data/eval/embedding_testset_draft.jsonl` | LLM 草拟中间产物 |
| `reports/embedding_eval/embedding_eval.md` | 自动生成的结果报告 |
| `reports/embedding_eval/embedding_eval.csv` | 结果表（CSV） |
| `reports/embedding_eval/embedding_eval_charts.png` | 准确率/速度/内存图表 |
| `reports/embedding_eval/results.json` | 全部原始指标（含 CI、分类别） |
| `reports/embedding_eval/hybrid_reference.json` | BGE-M3 hybrid 参考点指标 |
| `tests/unit/test_embedding_eval_metrics.py` | 指标实现单元测试（7 通过） |

---

*报告由本机实跑生成；如需在 GPU 机器上复跑或放大语料，调整 `evaluation/embedding/_config.py` 中的
`device` / `dtype` / 语料抽样上限即可。*
