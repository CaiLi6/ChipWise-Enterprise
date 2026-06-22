# ChipWise Enterprise 吞吐量 / QPS 测试报告

> 测试时间：2026-06-22  
> 测试对象：本机运行中的 ChipWise Enterprise FastAPI 服务 `http://localhost:8080`  
> 当前结论：**API 框架本身吞吐较高，真实 Agent 问答吞吐主要受 LM Studio 35B 推理和工具链耗时限制。**

## 1. 测试环境

运行状态：

- FastAPI Gateway：`0.0.0.0:8080`
- PostgreSQL：healthy
- Redis：healthy
- Milvus：healthy
- BGE-M3 Embedding：healthy
- bce-reranker：healthy
- LM Studio primary/router：healthy

测试前 `/readiness` 返回：

```json
{
  "status": "ready",
  "services": {
    "postgres": {"healthy": true},
    "redis": {"healthy": true},
    "milvus": {"healthy": true},
    "embedding": {"healthy": true},
    "reranker": {"healthy": true},
    "lmstudio_primary": {"healthy": true},
    "lmstudio_router": {"healthy": true}
  }
}
```

## 2. 测试方法

使用 Python `httpx.AsyncClient` 对不同类型接口进行并发请求：

1. `GET /health`：只测 FastAPI liveness。
2. `GET /readiness`：测依赖检查，包括 PG/Redis/Milvus/Embedding/Reranker/LM Studio。
3. `GET /api/v1/memory`：测鉴权 + PostgreSQL 轻查询。
4. `POST /api/v1/query`：测真实 Agent/RAG/LLM 查询。

真实 Agent 查询使用问题：

```text
PH2A106FLG900 的 DSP 数量是多少？
```

## 3. QPS 测试结果

| 场景 | 并发 | 请求数 | 成功 | QPS | 平均延迟 | 说明 |
|---|---:|---:|---:|---:|---:|---|
| `GET /health` | 50 | 300 | 300 | **717.7 QPS** | 0.064s | 只测 FastAPI 存活，最轻量 |
| `GET /readiness` | 5 | 30 | 30 | **3.57 QPS** | 1.40s | 会检查 PG/Redis/Milvus/Embedding/Reranker/LM Studio，较重 |
| `GET /api/v1/memory` | 20 | 100 | 100 | **824.4 QPS** | 0.022s | 鉴权 + PG 轻查询 |
| `POST /api/v1/query` 真实 Agent 单并发 | 1 | 3 | 3 | **0.076 QPS** | 13.2s | 端到端 Agent/RAG/LLM 查询 |
| `POST /api/v1/query` 真实 Agent 并发 2 | 2 | 4 | 4 | **0.051 QPS** | 39.4s | 并发后 LM Studio 35B 争用明显，吞吐反而下降 |

## 4. 结果解读

### 4.1 API 框架不是瓶颈

`/health` 和 `/api/v1/memory` 都达到数百 QPS：

- `/health`：约 **717.7 QPS**
- `/api/v1/memory`：约 **824.4 QPS**

说明 FastAPI、鉴权、轻量 PG 查询这类路径本身吞吐足够高。

### 4.2 `/readiness` 不是业务 QPS 指标

`/readiness` 只有约 **3.57 QPS**，原因是它会同步检查多个下游服务：

- PostgreSQL
- Redis
- Milvus
- Embedding service
- Reranker service
- LM Studio primary/router

这个接口适合健康检查，不适合作为系统业务吞吐指标。

### 4.3 真实 Agent 查询瓶颈在 LLM 和工具链

真实端到端 Agent 查询结果：

- 单并发：约 **0.076 QPS**
- 并发 2：约 **0.051 QPS**

并发 2 反而下降，说明当前硬件环境下 LM Studio 35B 主模型推理资源已经成为瓶颈，多请求并发会造成明显争用。

换算：

```text
0.05–0.08 QPS ≈ 3–5 个完整 Agent 查询 / 分钟
```

## 5. 当前容量判断

| 请求类型 | 规划 QPS |
|---|---:|
| 轻量 API / 管理接口 | 数百 QPS 级 |
| 健康检查 `/readiness` | 约 3–4 QPS |
| 完整 Agent/RAG/LLM 查询 | 约 0.05–0.08 QPS |
| 完整 Agent 查询折算 | 约 3–5 次 / 分钟 |

因此当前系统适合：

- 20 人团队内部使用；
- 查询量不高但需要高质量本地推理；
- 管理/记忆/文档类接口高频访问；
- Agent 查询需要排队或限流。

## 6. 优化建议

### 6.1 单参数问题增加 SQL Fast Path

例如：

```text
PH2A106FLG900 的 DSP 数量是多少？
```

这类问题不一定需要完整 Agent + 35B LLM，可以直接：

```text
意图识别 -> SQL 查询 chip_parameters -> grounding/citation -> 返回
```

预期收益：

- 延迟从 10+ 秒降到百毫秒级；
- QPS 提升一个数量级以上；
- 减少 LM Studio 主模型压力。

### 6.2 提高 SemanticCache 命中率

当前系统已有 Redis 语义缓存：

```text
gptcache:bucket:{bucket}
```

可以继续优化：

- 对标准单参数问题做 query normalization；
- 增加别名归一化，例如 `DSP 数量` / `DSP 个数`；
- 对高频查询预热缓存。

### 6.3 路由模型先判定是否需要 Agent

可以增加轻量 router：

```text
single_parameter_query -> SQL fast path
comparison_query       -> compare / rag
relationship_query     -> graph_query
open_query             -> full Agent
```

让 35B 主模型只处理复杂问题。

### 6.4 限制主模型并发

当前并发 2 下吞吐下降，建议：

- 保持 primary LLM 并发为 1–2；
- 使用队列或 semaphore；
- 前端显示排队/处理中状态；
- 对轻量查询走 fast path 绕过主模型。

### 6.5 继续观察指标

建议监控：

- Agent 平均延迟 / p95
- LLM tokens / request
- SemanticCache hit rate
- SQL fast path hit rate
- memory episode success rate
- grounding abstain rate
- LM Studio CPU/GPU/内存占用

## 7. 最终结论

当前系统吞吐可以概括为：

```text
FastAPI / 管理类接口：数百 QPS
完整 Agent RAG 查询：约 0.05–0.08 QPS
主要瓶颈：LM Studio 35B 主模型推理 + Agent 工具链
```

如果面试或汇报中需要一句话：

> 在单机本地 35B LLM 部署下，ChipWise 管理类 API 可达数百 QPS，完整 Agentic RAG 查询受本地大模型推理限制约 0.05–0.08 QPS；后续通过 SQL Fast Path、语义缓存和轻量路由可显著提升高频单参数查询吞吐。
