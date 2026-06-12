# Embedding 模型对比基准 (`evaluation/embedding/`)

量化对比文本 embedding 模型在 ChipWise 场景（**中文提问 → 检索英文/中英混合芯片 Datasheet**）下的
**检索准确率 / 推理速度 / 部署内存**，使用自建的、带分级相关度标注（qrels）的专业测试集。

最新一次运行结果见 [`reports/embedding_eval/embedding_eval.md`](../../reports/embedding_eval/embedding_eval.md)
（+ `.csv` + `_charts.png`）。

## 对比模型（默认集）

| key | HF id | 说明 |
|-----|-------|------|
| `bge-m3` | `BAAI/bge-m3` | 生产基准（dense 路径） |
| `bge-large-zh` | `BAAI/bge-large-zh-v1.5` | 中文检索指令（query 侧） |
| `jina-v3` | `jinaai/jina-embeddings-v3` | task LoRA，需 einops + remote code |
| `qwen3-0.6b` | `Qwen/Qwen3-Embedding-0.6B` | instruct prompt（query 侧），last-token pooling |
| `e5-large` | `intfloat/multilingual-e5-large` | 强制 `query:`/`passage:` 前缀 |

## 方法学要点

- **公平隔离**：固定共享 chunk 语料、统一 `max_len=512`、统一 `sentence-transformers` 后端、L2 归一化、
  关闭 reranker，主测用 **faiss 精确 cosine**（隔离 embedding 质量，不引入 ANN 误差）。
- **每模型独立子进程**：干净的内存测量（RSS + PSS + 冷加载/稳态/推理峰值 + 权重磁盘大小）。
- **专业测试集**：LLM 从真实 Datasheet 草拟双语 Q/A → 关键词逐字接地 → 多模型+BM25 **池化** →
  LLM 分级评判（0/1/2）→ 人工复核（`verified`），降低单源标注的假阴性。
- **统计稳健**：每个指标给出均值 + **bootstrap 95% 置信区间**（样本约 90），并分类别/分语言汇报。
- **参考点**：`bge-m3` hybrid (dense+sparse, RRF) 单独汇报，不参与纯 dense 排名。

详见仓库根 `docs/ENTERPRISE_DEV_SPEC.md` 与会话计划。

## 运行流程

```bash
pip install -r requirements-eval.txt          # torch CPU 需单独装 CPU wheel
# 结构化抽取/评判默认用 gemma-4-31b-it（干净 JSON）；可用 EMBED_EVAL_LLM 覆盖

python -m evaluation.embedding.cli build-corpus  --limit 60     # 真实 PDF → 冻结 chunk 语料
python -m evaluation.embedding.cli build-testset --n 90         # LLM 双语草拟
python -m evaluation.embedding.cli pool                         # 池化 + 分级评判 → qrels
python -m evaluation.embedding.cli review --sample 12           # 人工抽查
python -m evaluation.embedding.cli review --mark-verified       # 复核完成后标记
python -m evaluation.embedding.cli run    --models all          # 5 模型 dense 基准
python -m evaluation.embedding.cli hybrid                       # BGE-M3 dense+sparse 参考
python -m evaluation.embedding.cli report                       # 生成 md/csv/图表
```

工件：`data/eval/embedding_corpus.jsonl`、`data/eval/embedding_qrels.jsonl`、
`reports/embedding_eval/{results.json, embedding_eval.md, .csv, _charts.png}`、
逐模型缓存 `reports/embedding_eval/cache/<model>.json`（按 corpus+queries 哈希复用）。

## 环境注意

- **CPU-only**：本机无 CUDA/ROCm，全部 CPU 推理。`Qwen3-Embedding-0.6B`（decoder）最慢（~1 texts/s），
  因此默认语料抽样到约 1000 chunk。有 GPU 时可放大语料、改 `device`/dtype。
- **模型下载**：默认 HF endpoint（hf-mirror.com 与 huggingface_hub ≥1.0 的严格 metadata 校验不兼容）。
- **截断**：统一 `max_len=512`，约 10–19% 的 chunk 被截断（已在报告"公平性审计"中按模型列出）。
