# 记忆系统上线与效果验收 Checklist

> 适用范围：Redis 短期记忆、SemanticCache、Agent 工作记忆、PG/Milvus/Kùzu 长期记忆、情节/过程/治理记忆、Claude Code 风格 checkpoint compaction、前端 `/memory` 页面。

## 1. 上线前置条件

- [ ] 已拉取最新代码，包含提交 `344e7aa feat: add checkpoint memory compaction` 或更新版本。
- [ ] `.env` 已配置 `PG_PASSWORD`、`REDIS_PASSWORD`、`JWT_SECRET_KEY`。
- [ ] PostgreSQL、Redis、Milvus、Kùzu 可用。
- [ ] LM Studio primary/router 模型已加载。
- [ ] BGE-M3 embedding 服务可用。
- [ ] 前端已重新 build/deploy。

## 2. 数据库迁移

必须执行：

```bash
alembic upgrade head
```

确认新表存在：

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('memory_episodes', 'memory_procedures', 'memory_records');
```

预期：

- [ ] `memory_episodes`
- [ ] `memory_procedures`
- [ ] `memory_records`

## 3. 配置核对

`config/settings.yaml` 应包含：

```yaml
memory:
  enabled: true
  session_ttl: 1800
  max_turns: 10
  compression_threshold: 10
  summary_max_chars: 2000
  compaction_budget_chars: 8000
  checkpoint_limit: 5
  pinned_limit: 20
  session_id_max_length: 128
  prompt_budget_chars: 6000
  recent_turns_always: 4
  min_relevance_score: 0.12
  llm_summarization_enabled: false
  summarizer_role: "router"
```

检查点：

- [ ] `memory.enabled=true`
- [ ] `cache.enabled=true`
- [ ] `agent.max_observation_chars` 不为空
- [ ] `retrieval.sparse_method` 符合当前 Milvus 能力

## 4. 后端功能验收

### 4.1 短期会话记忆

步骤：

1. 使用同一个 `session_id` 连续提问：
   - “XCKU5PFFVD900 的 PCIe 用户时钟是多少？”
   - “它的 DSP 数量呢？”
2. 查看 Redis：

```bash
redis-cli -a "$REDIS_PASSWORD" keys 'session:*'
```

预期：

- [ ] Redis 出现 `session:{user_key}:{session_id}`。
- [ ] payload 中有 `version=2`。
- [ ] payload 中有 `summary`、`turns`、`entities`。
- [ ] 第二轮问题能利用第一轮上下文。

### 4.2 checkpoint compaction

步骤：

1. 用同一个 session 连续问 10 轮以上，或发送长文本让上下文超过 `compaction_budget_chars`。
2. 查看 Redis session payload。

预期：

- [ ] `checkpoints` 非空。
- [ ] `summary` 被更新。
- [ ] `turns` 只保留最近若干条。
- [ ] `pinned` 中保留用户显式“记住/以后/默认”等偏好。

### 4.3 SemanticCache

步骤：

1. 连续两次问语义相近的问题。
2. 查看 trace 或日志。

预期：

- [ ] 第二次查询出现 `cache_lookup.hit=true` 或 `cache_hit` stage。
- [ ] cache hit 仍写入短期会话。
- [ ] 拒答或 early-stop 不写入 cache。

### 4.4 情节记忆

执行查询后检查：

```sql
SELECT query_text, tools_used, outcome, created_at
FROM memory_episodes
ORDER BY created_at DESC
LIMIT 5;
```

预期：

- [ ] 每次 query 生成 episode。
- [ ] `tools_used` 有 Agent 工具链。
- [ ] `outcome` 是 `success` / `cache_hit` / `abstained` / stopped reason。
- [ ] `citations`、`grounding` 有记录。

### 4.5 过程记忆

执行多次成功查询后检查：

```sql
SELECT id, intent, recommended_tools, success_count, failure_count
FROM memory_procedures
ORDER BY updated_at DESC
LIMIT 10;
```

预期：

- [ ] 成功 episode 会更新 learned procedure。
- [ ] 类似“主频/DSP/IO/PCIe”问题能获得 SQL-first hint。
- [ ] 替代/兼容问题能获得 graph-first hint。

### 4.6 治理记忆

显式记忆：

```text
以后默认优先用 sql_query 查单参数。
```

检查：

```sql
SELECT scope, kind, content, source, status
FROM memory_records
ORDER BY created_at DESC
LIMIT 5;
```

预期：

- [ ] 显式“记住/以后/默认”生成 confirmed user memory。
- [ ] 高质量 episode 生成 candidate project memory。
- [ ] 只有 confirmed memory 会注入 prompt。

## 5. 前端验收

访问：

```text
/memory
```

预期：

- [ ] 记忆管理入口出现在侧边栏。
- [ ] 可查看 confirmed/candidate/rejected 记忆。
- [ ] 可创建 user/project memory。
- [ ] 可确认、拒绝、删除记忆。
- [ ] 可查看 query episodes。
- [ ] 普通查询页面 `/query` 不受影响。

## 6. 观测指标

建议上线后观察：

| 指标 | 目标 |
|---|---|
| Redis session 写入成功率 | > 99% |
| QueryRewriter 触发后正确率 | 人工抽样 > 90% |
| SemanticCache hit rate | 稳定后逐步上升 |
| memory_episodes 写入数 | 与 query 数基本一致 |
| checkpoint 触发次数 | 长会话中可见，短会话中较少 |
| grounding abstain rate | 不因记忆注入明显升高 |
| candidate memory 确认率 | 用于判断自动巩固质量 |

## 7. 回归测试命令

后端：

```bash
.venv/bin/pytest -q tests/unit/test_memory_advanced.py \
  tests/unit/test_memory_retriever.py \
  tests/unit/test_conversation_manager.py \
  tests/unit/test_query_smoke_e2e.py \
  tests/unit/test_semantic_cache.py \
  tests/unit/test_tool_registry.py

.venv/bin/python -m compileall src
```

前端：

```bash
npm --prefix frontend/web run build
```

## 8. 上线判断

可以认为记忆系统正式上线的条件：

- [ ] `alembic upgrade head` 成功。
- [ ] FastAPI 重启后 `/api/v1/memory` 可访问。
- [ ] `/memory` 前端页面可用。
- [ ] Redis session payload 有 v2 + summary/turns/entities/pinned/checkpoints。
- [ ] `memory_episodes` 持续写入。
- [ ] 至少一条 explicit confirmed memory 能被保存并在后续查询中注入。
- [ ] 长会话能触发 checkpoint compaction。
- [ ] golden/真实查询抽样没有因记忆注入导致 grounding 质量下降。

## 9. 常见问题

**没有写入 memory_episodes**：

- 检查 `alembic upgrade head` 是否执行。
- 检查 PostgreSQL 连接池是否可用。
- 查看 FastAPI 日志中 `Episode/procedure memory recording failed`。

**没有 Redis session**：

- 检查 Redis 是否可用。
- 检查 `memory.enabled`。
- 检查请求是否带合法 `session_id`。

**记忆污染**：

- candidate memory 默认不会进入 prompt。
- 删除或拒绝有问题的 `memory_records`。
- 检查 grounding/eval 指标，必要时提高 consolidation 阈值。

**压缩丢失重要信息**：

- 检查 `pinned` 是否捕获偏好/高重要性内容。
- 增大 `summary_max_chars` 或 `checkpoint_limit`。
- 开启 `llm_summarization_enabled` 后重新评估摘要质量。
