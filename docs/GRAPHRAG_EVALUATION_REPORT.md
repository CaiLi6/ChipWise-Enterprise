# GraphRAG 知识图谱效果评测报告

> 测试时间：2026-06-24  
> 评测命令：`python -m src.evaluation.cli graph --limit-per-type 20 --output reports/eval/graphrag_eval_latest.json`  
> 报告文件：`reports/eval/graphrag_eval_latest.json`

## 1. 评测方法

本次新增了确定性 GraphRAG 评测模块：

- `src/evaluation/graphrag.py`
- CLI 子命令：`python -m src.evaluation.cli graph`
- 单测：`tests/unit/test_graphrag_evaluation.py`

评测不依赖 LLM-as-judge，而是用 PostgreSQL 中的源数据自动构建 golden cases，再用 Kùzu/GraphSearch 查询结果做确定性比对。

评测维度：

| 维度 | 指标 | 含义 |
|---|---|---|
| 图谱覆盖 | node/edge coverage | PG 源数据同步到 Kùzu 的覆盖率 |
| 替代关系召回 | alternative_recall | `ALTERNATIVE` 边能否查回期望替代料 |
| 参数范围召回 | param_range_recall | 参数节点和 `HAS_PARAM` 边能否支持范围查询 |
| 子图正确性 | subgraph_recall | 芯片一跳子图是否能返回足够节点/边 |
| 延迟 | avg_latency_ms | 图查询平均延迟 |
| 总体通过率 | pass_rate | golden cases 的通过比例 |

## 2. 当前图谱规模

PostgreSQL 源数据：

| 类型 | 数量 |
|---|---:|
| chips | 591 |
| chip_parameters | 3068 |
| documents | 213 |
| chip_alternatives | 589 |
| design_rules | 390 |
| errata | 0 |

Kùzu 图谱数据：

| 类型 | 数量 |
|---|---:|
| Chip nodes | 284 |
| Parameter nodes | 3069 |
| Document nodes | 216 |
| DesignRule nodes | 390 |
| Errata nodes | 0 |
| HAS_PARAM edges | 3069 |
| ALTERNATIVE edges | 141 |
| DOCUMENTED_IN edges | 216 |
| HAS_RULE edges | 390 |
| HAS_ERRATA edges | 0 |

## 3. 覆盖率结果

| 指标 | 结果 |
|---|---:|
| chip_node_coverage | 0.4805 |
| parameter_node_coverage | 1.0000 |
| document_node_coverage | 1.0000 |
| design_rule_node_coverage | 1.0000 |
| errata_node_coverage | 1.0000* |
| has_param_edge_coverage | 1.0000 |
| alternative_edge_coverage | 0.2394 |
| documented_in_edge_coverage | 1.0000 |
| has_rule_edge_coverage | 1.0000 |
| has_errata_edge_coverage | 1.0000* |
| mean_non_empty_coverage | 0.8400 |

> `errata=0`，所以 errata 覆盖率在数学上为 1.0，但业务上代表“当前没有可评测勘误数据”，不能说明 errata 图谱效果好。

## 4. 检索质量结果

共构建 60 条 deterministic graph golden cases：

| 指标 | 结果 |
|---|---:|
| case_count | 60 |
| pass_rate | 0.9333 |
| mean_recall | 0.9333 |
| avg_latency_ms | 5.39 ms |
| alternative_pass_rate | 0.8500 |
| alternative_recall | 0.8500 |
| param_range_pass_rate | 0.9500 |
| param_range_recall | 0.9500 |
| subgraph_pass_rate | 1.0000 |
| subgraph_recall | 1.0000 |

## 5. 代表性结果

### 5.1 PH2A106FLG900 替代关系

图谱能查到：

```text
PH2A106FLG900 -> XCKU5PFFVD900
compat_type = drop_in
compat_score = 1.0
```

这说明核心的兼容/替代关系已经进入 Kùzu，并能被 `graph_query` 使用。

### 5.2 参数和子图

参数范围查询和子图查询效果较好：

- `param_range_recall = 0.95`
- `subgraph_recall = 1.0`

说明 `Chip -> Parameter`、`Chip -> Document`、`Chip -> DesignRule` 这几类结构化边基本可用。

## 6. 主要短板

### 6.1 Chip node coverage 只有 48.05%

PG 中有 591 个 chip，而 Kùzu 中有 284 个 Chip 节点。

原因：

- Kùzu 主要同步 ingestion/graph sync 覆盖到的芯片；
- PG 中有不少 chip 是 referenced/seed/噪声型 part number；
- 需要进一步清理 PG 中非芯片 token，或补全 Kùzu 全量同步任务。

### 6.2 Alternative edge coverage 只有 23.94%

PG 中有 589 条 `chip_alternatives`，Kùzu 中有 141 条 `ALTERNATIVE` 边。

原因：

- 部分 alternative target 没有对应 Chip node，Kùzu `MATCH` 不到两端节点时无法建边；
- PG 中有一些噪声替代关系，例如电压、内存类型、文档 token 被识别成 part number；
- 需要做 alternative 清洗、两端节点补建、重新 graph sync。

### 6.3 Errata 图谱当前无数据

`errata=0`，所以当前无法评估勘误类多跳推理。

下一步需要：

- 补 errata 文档；
- 提升 errata parser；
- 建 `Chip -> Errata -> Peripheral` 的真实数据集。

## 7. 结论

当前知识图谱效果可以概括为：

```text
结构化参数图谱和芯片子图已经比较可用；
核心替代关系可查，但全量替代边覆盖不足；
errata 类图谱还没有形成有效数据；
整体 deterministic GraphRAG case pass rate = 93.33%，平均查询延迟约 5.39 ms。
```

## 8. 面试回答版本

如果面试官问“你的知识图谱效果如何？”，可以这样回答：

> 我们对 GraphRAG 做了确定性评测，不依赖 LLM 评判，而是用 PostgreSQL 源数据自动生成 graph golden cases，再用 Kùzu 查询结果计算覆盖率、关系召回、路径正确性和延迟。当前图谱在 60 条 golden cases 上总体通过率 93.33%，参数范围召回 95%，芯片子图召回 100%，平均图查询延迟约 5.39ms；PH2A106FLG900 这类核心芯片已经能查到 XCKU5PFFVD900 的 drop-in 替代关系。短板是全量 Chip 节点覆盖约 48%，Alternative 边覆盖约 24%，主要受 PG 中噪声 part number 和部分替代关系两端节点未同步影响；errata 数据目前为空，所以勘误多跳推理还需要补数据。整体上，图谱对参数、子图和核心兼容关系已经可用，但仍需要继续做数据清洗和全量同步来提升覆盖率。

## 9. 后续优化

1. 增加全量 PG→Kùzu sync job，确保所有合法 chip 节点进入图谱。
2. 清理 PG 中非芯片 part number 噪声。
3. 对 `chip_alternatives` 两端节点做预同步，提升 ALTERNATIVE 边覆盖。
4. 补 errata 数据集和 parser，建立真实 `Chip -> Errata -> Peripheral` 测试集。
5. 增加 RAG vs GraphRAG ablation，对比图谱增强前后的 answer quality。
