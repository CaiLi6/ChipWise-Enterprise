# ChipWise Enterprise 记忆系统设计与实现

> 范围：后端短期会话记忆、语义缓存、Agent 工作记忆、长期知识记忆、前端本地会话、Trace/评估记忆。  
> 当前状态：后端 `/api/v1/query` 与 `/api/v1/query/stream` 已接入短期记忆加载、QueryRewriter、SemanticCache、Agent history、写回与压缩流程。

## 1. 整体设计理念

ChipWise 的记忆系统采用分层架构，不把所有上下文都塞进 LLM prompt，而是按生命周期、可信边界和访问方式拆分：

1. **短期记忆**：当前用户、当前会话的多轮上下文，存 Redis，有 TTL，可压缩，可恢复，并带重要性/主题/实体评分。
2. **语义缓存**：相似问题的结果复用，存 Redis，用 embedding + cosine 判断命中。
3. **Agent 工作记忆**：单次 ReAct 推理过程中的 system prompt、history、tool observations，受 token budget 管理。
4. **长期知识记忆**：跨用户、跨会话的芯片知识，存 PostgreSQL、Milvus、Kùzu。
5. **前端本地记忆**：浏览器 UX 层的多会话展示，存 localStorage，不作为后端可信上下文来源。
6. **Trace/评估记忆**：查询轨迹、citations、grounding、评估指标，存 JSONL，用于调试和质量闭环。

核心原则：

- 后端以 authenticated user identity 隔离记忆，不信任前端 username。
- Redis 记忆是可丢失、可过期、可降级的短期上下文，不承担永久知识沉淀。
- 长期知识由 ingestion 写入 PG/Milvus/Kùzu，Agent 通过工具读取。
- Prompt 中只放压缩摘要和最近 turns，避免上下文无限增长。
- 标准查询和 SSE 查询复用同一套后端记忆流程。

## 2. 长短期记忆组成

| 类型 | 组成 | 存储位置 | 主要职责 |
|---|---|---|---|
| 短期会话记忆 | compressed summary + scored turns + entities | Redis `session:{user_key}:{session_id}` | 多轮上下文、指代恢复、当前会话连续性、按预算注入 |
| 语义结果记忆 | query embedding + response + tools/citations metadata | Redis `gptcache:bucket:{bucket}` | 相似查询快速返回，减少重复 RAG/LLM 成本 |
| Agent 工作记忆 | system prompt + history + current query + tool observations | 进程内 Python list | 单次 ReAct 推理上下文 |
| 长期结构化记忆 | chips、parameters、documents、rules、errata、alternatives | PostgreSQL | 精确参数查询、审计、结构化关系源数据 |
| 长期向量记忆 | datasheet chunks、knowledge notes embeddings | Milvus | RAG 语义检索、BM25/hybrid 检索 |
| 长期图谱记忆 | Chip/Parameter/Errata/Document/DesignRule/Peripheral 图 | Kùzu | Graph RAG、多跳关系、替代料/errata 查询 |
| 情节记忆 | query、tools、citations、grounding、outcome | PostgreSQL `memory_episodes` | 查询回放、经验沉淀、失败规避 |
| 过程记忆 | intent、trigger patterns、recommended tools、stop rules | PostgreSQL `memory_procedures` + 内置默认策略 | 工具选择经验、成功路径复用 |
| 治理记忆 | user/project memory records | PostgreSQL `memory_records` | 用户显式记忆、项目候选记忆、确认/拒绝/删除 |
| 前端本地记忆 | chat sessions、current session id、token/user | localStorage | 浏览器多会话 UX 和登录态 |
| 观测/评估记忆 | trace stages、eval metrics、batch metadata | `logs/*.jsonl` | 回放、质量评估、调试 |

## 3. 后端短期记忆

实现位置：

- `src/core/conversation_manager.py`
- `src/api/dependencies.py`
- `src/api/routers/query.py`

### 3.1 Redis key

```text
session:{user_key}:{session_id}
```

`user_key` 来自当前认证用户：

```text
current_user.sub || current_user.username || "anonymous"
```

`session_id` 来自前端，但后端会校验：

```text
^[A-Za-z0-9_.:-]{1,128}$
```

非法 `session_id` 返回 400，不进入 Redis key。

### 3.2 存储格式

当前 payload 版本为 v2：

```json
{
  "version": 2,
  "summary": "压缩后的早期会话事实摘要",
  "turns": [
    {
      "role": "user",
      "content": "先看 XCKU5PFFVD900",
      "created_at": 1710000000.0,
      "metadata": {
        "importance": 0.78,
        "topics": ["parameter_query"],
        "entities": {"chips": ["XCKU5PFFVD900"]},
        "facts": ["先看 XCKU5PFFVD900"]
      }
    },
    {
      "role": "assistant",
      "content": "已找到相关资料",
      "created_at": 1710000001.0
    }
  ],
  "entities": {
    "chips": ["XCKU5PFFVD900"]
  },
  "updated_at": 1710000001.0
}
```

兼容策略：

- 旧版 JSON list 会自动迁移为 v2 payload。
- corrupt JSON 会记录 warning 并返回空上下文，不阻塞查询。
- key TTL 默认 1800 秒，可通过 `config/settings.yaml::memory.session_ttl` 配置。

### 3.3 配置

```yaml
memory:
  enabled: true
  session_ttl: 1800
  max_turns: 10
  compression_threshold: 10
  summary_max_chars: 2000
  session_id_max_length: 128
  prompt_budget_chars: 6000
  recent_turns_always: 4
  min_relevance_score: 0.12
  llm_summarization_enabled: false
  summarizer_role: "router"
```

字段含义：

| 字段 | 含义 |
|---|---|
| `enabled` | 是否启用后端短期会话记忆 |
| `session_ttl` | Redis session key 过期时间 |
| `max_turns` | prompt 中保留的最近消息数 |
| `compression_threshold` | 超过多少条 turns 后触发压缩 |
| `summary_max_chars` | compressed summary 最大字符数 |
| `session_id_max_length` | session_id 最大长度 |
| `prompt_budget_chars` | 注入 Agent prompt 的记忆最大字符预算 |
| `recent_turns_always` | 无论相关性如何都保留的最近消息数 |
| `min_relevance_score` | 非最近消息进入 prompt 的最低相关性 |
| `llm_summarization_enabled` | 是否启用 LLM 结构化摘要 |
| `summarizer_role` | 摘要模型角色，默认 router |

## 4. 短期记忆运行流程

### 4.1 加载流程

```text
/query or /query/stream
  -> current_user
  -> validate session_id
  -> ConversationManager.load_context(user_key, session_id)
  -> return ConversationContext(summary, turns, entities)
  -> MemoryRetriever.select_messages(context, query)
  -> prompt-budgeted messages
```

`to_messages()` 输出：

```json
[
  {
    "role": "system",
    "content": "Conversation summary (compressed memory):\n..."
  },
  {
    "role": "user",
    "content": "最近一条用户消息"
  },
  {
    "role": "assistant",
    "content": "最近一条助手回复"
  }
]
```

如果没有 summary，则只返回被 MemoryRetriever 选中的 recent/relevant turns。

MemoryRetriever 的选择依据：

- 当前 query 与 turn 内容的关键词重叠；
- 芯片实体是否重合；
- turn metadata 中的 `importance`；
- 是否属于最近 `recent_turns_always` 条消息；
- 总字符数是否超过 `prompt_budget_chars`。

### 4.2 改写流程

实现位置：

- `src/core/query_rewriter.py`
- `config/prompts/query_rewriter.txt`

流程：

```text
raw_query + history
  -> QueryRewriter._needs_rewrite()
  -> router LLM rewrite when pronoun/ellipsis exists
  -> rewritten_query
```

例子：

```text
history: 用户之前问过 XCKU5PFFVD900
raw_query: 它的 PCIe 用户时钟是多少？
rewritten_query: XCKU5PFFVD900 的 PCIe 用户时钟是多少？
```

降级策略：

- 没有 history：不改写。
- 没有代词/省略：不调用 LLM。
- LLM 不可用或返回空：使用原始 query。

### 4.3 写入流程

标准查询成功后：

```text
Agent result
  -> grounding
  -> ConversationManager.append_exchange(user raw query, assistant grounded answer)
  -> Redis SET with TTL
```

cache hit 也会写入本轮 user/assistant exchange，保证会话连续。

SSE 查询：

- Agent 完整执行后再分块发给前端；
- done 前已获得完整 grounded answer；
- 客户端断开时不保存半截 assistant turn。

### 4.4 压缩流程

当 `turns` 数量超过 `compression_threshold`：

```text
turns = old_turns + recent_turns
old_turns -> summary
recent_turns -> keep max_turns
summary + recent_turns -> Redis payload
```

当前实现包含 `MemorySummarizer` 扩展点。默认使用确定性 fallback 摘要；开启 `llm_summarization_enabled` 后，可使用 router LLM 生成结构化摘要。摘要固定保留：

- 已确认事实；
- 用户偏好；
- 当前目标；
- 未完成问题；
- 关键实体。

摘要会裁剪到 `summary_max_chars`，避免压缩记忆无限增长。

压缩目标：

- 保留用户已讨论芯片、参数、意图、未完成问题；
- 删除冗余寒暄和重复文本；
- 避免 prompt 随会话线性增长。

### 4.5 恢复流程

恢复来源：

1. Redis v2 payload：直接恢复 summary + recent turns。
2. Redis legacy list：迁移为 v2 payload 后恢复。
3. Redis key 过期/不存在：返回空上下文。
4. Redis corrupt JSON：记录 warning，返回空上下文。
5. Redis 不可用：记录 `memory_degraded` trace，单轮查询继续执行。

## 5. 语义缓存

实现位置：

- `src/cache/semantic_cache.py`
- `src/api/dependencies.py`
- `src/api/routers/query.py`

### 5.1 配置

```yaml
cache:
  enabled: true
  similarity_threshold: 0.95
  ttl_conversational: 3600
  ttl_comparison: 14400
  bucket_size: 8
```

### 5.2 Redis key 与数据格式

```text
gptcache:bucket:{bucket_key}
```

每个 bucket 是 Redis list，entry 格式：

```json
{
  "query": "rewritten query",
  "vector": [0.1, 0.2],
  "response": {
    "answer": "...",
    "citations": [],
    "trace_id": "..."
  },
  "tools_used": ["rag_search"],
  "metadata": {
    "session_id": "s_...",
    "user_key": "u-1",
    "citation_count": 2
  },
  "created_at": 1710000000.0
}
```

### 5.3 查询流程

```text
rewritten_query
  -> BGE-M3 dense embedding
  -> LSH bucket key
  -> Redis LRANGE bucket
  -> cosine similarity
  -> similarity >= threshold: cache hit
```

cache hit：

1. 返回 cached answer/citations；
2. 写入本轮短期会话；
3. 记录 `cache_lookup`、`cache_hit`、`response` trace；
4. 可进入在线评估采样。

cache miss：

1. 进入 AgentOrchestrator；
2. grounding 后判断是否可缓存；
3. 成功回答写入 cache。

不缓存：

- 空答案；
- Agent early-stop；
- grounding hard-abstain；
- 错误响应。

## 6. Agent 工作记忆

实现位置：

- `src/agent/orchestrator.py`
- `src/agent/prompt_builder.py`
- `config/prompts/agent_system.txt`

消息顺序：

```text
system prompt
  -> compressed memory summary
  -> recent conversation turns
  -> current rewritten query
  -> assistant tool calls
  -> tool observations
```

限制：

- `agent.max_total_tokens` 控制总 token budget。
- `agent.max_observation_chars` 截断工具 observation。
- system prompt 要求工具优先、少轮次、数值必须来自 tool result。

## 7. 长期知识记忆

长期知识不存入 Redis session，而由 ingestion 和 Agent tools 维护/读取。

### 7.1 PostgreSQL

Schema：

- `alembic/versions/001_initial_schema.py`
- `alembic/versions/002_kg_metadata.py`

关键表：

| 表 | 职责 |
|---|---|
| `chips` | 芯片主数据 |
| `chip_parameters` | 参数精确查询 |
| `documents` | 文档元数据 |
| `knowledge_notes` | 团队知识沉淀 |
| `chip_alternatives` | 替代/兼容关系 |
| `design_rules` | 设计规则 |
| `errata` | 勘误信息 |
| `query_audit_log` | 查询审计预留 |

### 7.2 Milvus

Collection：

- `datasheet_chunks`
- `knowledge_notes`

字段包括：

- dense vector；
- sparse vector；
- BM25 vector；
- chip/document metadata；
- raw content。

读取工具：

- `rag_search`
- `knowledge_search`

### 7.3 Kùzu

节点：

- `Chip`
- `Parameter`
- `Errata`
- `Document`
- `DesignRule`
- `Peripheral`

关系：

- `HAS_PARAM`
- `ALTERNATIVE`
- `HAS_ERRATA`
- `ERRATA_AFFECTS`
- `DOCUMENTED_IN`
- `HAS_RULE`
- `HAS_PERIPHERAL`

读取工具：

- `graph_query`

### 7.4 写入流程

文档 ingestion：

```text
upload document
  -> documents row
  -> extract PDF pages
  -> chunk pages
  -> BGE-M3 embeddings
  -> Milvus datasheet_chunks
  -> extract parameters/design rules/errata/alternatives
  -> PostgreSQL rows
  -> GraphSynchronizer
  -> Kùzu graph
```

实现位置：

- `src/api/routers/documents.py`
- `src/ingestion/graph_sync.py`
- `src/libs/vector_store/milvus_store.py`
- `src/libs/graph_store/kuzu_store.py`

## 8. 情节记忆、过程记忆与治理记忆

新增迁移：

- `alembic/versions/003_memory_system.py`

新增核心模块：

- `src/core/episodic_memory.py`
- `src/core/procedural_memory.py`
- `src/core/memory_governance.py`
- `src/core/memory_consolidator.py`

### 8.1 情节记忆：`memory_episodes`

每次查询会生成一个 episode，用于后续回放、评估、过程学习和候选记忆生成。

```json
{
  "id": "...",
  "user_key": "u-1",
  "session_id": "s1",
  "trace_id": "...",
  "query_text": "原始问题",
  "rewritten_query": "改写后的问题",
  "tools_used": ["sql_query", "rag_search"],
  "citations": [{"chunk_id": "c1"}],
  "grounding": {"coverage": 0.95, "abstained": false},
  "eval_metrics": {},
  "answer_preview": "答案摘要",
  "outcome": "success|cache_hit|abstained|error",
  "created_at": "..."
}
```

写入时机：

- cache hit：记录 `outcome=cache_hit`。
- Agent 成功：记录 `outcome=success`。
- grounding 拒答：记录 `outcome=abstained`。
- 早停或错误：记录 stopped reason。

DB 不可用时，episode 写入 no-op，不影响用户响应。

### 8.2 过程记忆：`memory_procedures`

过程记忆保存“某类问题适合什么工具链”的可复用策略。

来源：

1. 内置默认策略：
   - 单参数/数值问题：`sql_query -> rag_search`
   - 替代/兼容关系：`graph_query -> rag_search`
   - 设计规则/errata：`rag_search -> graph_query`
2. 成功 episode 自动更新：
   - 根据 query intent 和 tools_used upsert 到 `memory_procedures`。

查询时：

```text
rewritten_query
  -> ProceduralMemoryStore.get_hints()
  -> format_hints()
  -> 注入 Agent system message
```

过程记忆只是 advisory hint，不能绕过 grounding 或 citations。

### 8.3 治理记忆：`memory_records`

治理记忆是可查看、确认、拒绝、删除的 user/project memory。

```json
{
  "id": "...",
  "scope": "user|project",
  "owner_key": "u-1|null",
  "kind": "note|preference|procedure_hint|lesson",
  "content": "...",
  "tags": ["explicit", "episode"],
  "source": "manual|user_explicit|episode",
  "source_id": "...",
  "status": "candidate|confirmed|rejected",
  "metadata": {},
  "use_count": 0
}
```

进入 prompt 的规则：

- 只有 `status=confirmed` 的 user/project memories 会被注入。
- candidate 仅作为候选，不进入 Agent prompt。
- 用户显式“记住/以后/remember”会创建 confirmed user memory。
- 高质量 episode 会创建 candidate project memory，等待确认。

API：

- `GET /api/v1/memory`
- `POST /api/v1/memory`
- `PATCH /api/v1/memory/{memory_id}/status`
- `DELETE /api/v1/memory/{memory_id}`
- `GET /api/v1/memory/episodes`

前端页面：

- `/memory`
- `frontend/web/src/views/MemoryView.vue`
- `frontend/web/src/api/memory.ts`

能力：

- 查看 confirmed/candidate/rejected 记忆；
- 手动创建 user/project 记忆；
- 确认、拒绝、删除候选记忆；
- 查看最近 query episodes、工具链路和 outcome。

### 8.4 评估驱动候选记忆

`MemoryConsolidator` 会从高质量 episode 中提议 candidate memory。

候选条件：

- `outcome=success`
- citations 数量达标
- grounding 未 abstain
- grounding coverage 达到阈值

候选不会自动生效，必须通过治理 API 确认为 `confirmed` 后才会进入 prompt。

## 9. 长期记忆工具接入

`query.py` 现在手动注册依赖型工具：

- `RAGSearchTool(hybrid, reranker, graph_search)`
- `GraphQueryTool(graph_search)`
- `SQLQueryTool(db_pool=db_pool)`
- `KnowledgeSearchTool(hybrid_search=hybrid)`

同时 `ToolRegistry.discover(skip_names={...})` 跳过依赖型工具的空实例：

```python
registry.discover(skip_names={"sql_query", "knowledge_search"})
```

这样 Agent 不会看到“可调用但无 DB/search 依赖”的 `sql_query` 或 `knowledge_search`。

## 10. 前端本地记忆

实现位置：

- `frontend/web/src/stores/query.ts`
- `frontend/web/src/stores/auth.ts`
- `frontend/web/src/views/QueryView.vue`
- `frontend/web/src/views/MemoryView.vue`

### 9.1 Chat sessions

localStorage keys：

```text
chipwise_sessions_v1::<username|guest>
chipwise_current_session::<username|guest>
```

数据结构：

```ts
interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: number
  updatedAt: number
}
```

职责：

- 前端多会话展示；
- 流式 token 拼接；
- citations 附加到最后一条 assistant 消息；
- 切账号重载对应 username bucket。

注意：

- 前端 localStorage 是 UX 层缓存，不是后端可信记忆。
- 后端只信任 JWT current_user 和 Redis 中对应 user_key 的 session。

### 9.2 Auth token

localStorage keys：

```text
chipwise_token
chipwise_refresh_token
chipwise_user
```

职责：

- axios 自动注入 Authorization；
- access token 到期前刷新；
- SSE 401 refresh 后重试一次。

风险：

- token 明文在 localStorage，仍有 XSS 风险。
- 后续可考虑 httpOnly secure cookie 保存 refresh token。

## 11. Trace 与评估记忆

Trace：

- 写入 `logs/traces.jsonl`
- 查询 API：`src/api/routers/traces.py`

记录阶段包括：

- `request`
- `memory_load`
- `memory_degraded`
- `query_rewrite`
- `governed_memory`
- `procedural_memory`
- `cache_lookup`
- `cache_hit`
- `iteration`
- `grounding`
- `memory_store`
- `cache_store`
- `episodic_memory`
- `response`
- `error`

Evaluation：

- 写入 `logs/evaluations.jsonl`
- 批处理写入 `logs/eval_batches.jsonl`
- 在线采样由 `src/evaluation/online_sampler.py` 触发。

## 12. 端到端运行流程

### 11.1 非流式查询

```text
POST /api/v1/query
  -> validate query/session
  -> load Redis memory
  -> rewrite query when needed
  -> semantic cache lookup
     -> hit: return cached response
     -> miss:
        -> load confirmed governed memories
        -> load procedural memory hints
        -> AgentOrchestrator.run(rewritten_query, conversation_history)
        -> tools read PG/Milvus/Kùzu
        -> extract citations
        -> grounding
        -> write short-term memory
        -> write episodic memory
        -> update procedural memory
        -> create explicit/candidate governed memories when applicable
        -> write semantic cache when safe
        -> trace/eval
        -> JSON response
```

### 11.2 SSE 查询

```text
POST /api/v1/query/stream
  -> same backend memory/cache/agent flow
  -> split grounded answer into small chunks
  -> data: token frames
  -> data: done frame with citations/trace_id/grounding
```

## 13. 降级策略

| 故障 | 行为 |
|---|---|
| Redis 不可用 | 跳过短期记忆和语义缓存，单轮 Agent 查询继续 |
| session corrupt JSON | warning + 空上下文，查询继续 |
| QueryRewriter LLM 不可用 | 使用原始 query |
| SemanticCache embedding/Redis 失败 | 视为 cache miss |
| Episodic/procedural/governed memory DB 不可用 | no-op，查询继续 |
| Agent tool 后端不可用 | 工具返回 error，Agent 按现有策略处理 |
| grounding 失败 | 使用原 answer，记录 warning |

## 14. 测试覆盖

相关测试：

- `tests/unit/test_conversation_manager.py`
- `tests/unit/test_semantic_cache.py`
- `tests/unit/test_query_rewriter.py`
- `tests/unit/test_query_smoke_e2e.py`
- `tests/unit/test_tool_registry.py`
- `tests/unit/test_memory_retriever.py`
- `tests/unit/test_memory_advanced.py`

覆盖点：

- v2 session payload；
- legacy list 迁移；
- corrupt JSON 降级；
- turn 压缩与 summary；
- importance/topic/entity/fact metadata；
- prompt-budgeted MemoryRetriever；
- configurable semantic cache TTL/bucket；
- query 路由传入 backend history；
- query 成功后写回 assistant answer；
- dependency tools auto-discover skip。
- episodic memory no-op degradation；
- procedural default hints and formatting；
- explicit user memory capture；
- high-quality episode candidate consolidation。

## 15. 剩余风险与后续优化

1. `ConversationManager` 当前仍是读-改-写模式；高并发同一 session 可进一步改为 Redis transaction 或 Lua。
2. fallback 压缩是确定性摘要；如需要更强摘要质量，可接入 router LLM summarizer。
3. SemanticCache 的 LSH 分桶仍较简单，后续可增加多 bucket probe 或倒排索引。
4. cache invalidation 当前仍是 bucket scan + query 字符串匹配，规模扩大后应改为 metadata index。
5. 前端 token/localStorage 仍有 XSS 风险，可规划 httpOnly cookie 化。

## 16. 最终状态

当前实现已经从“前端本地多会话 + 后端单轮 Agent”升级为：

```text
后端 Redis 短期记忆
  + QueryRewriter 上下文改写
  + SemanticCache 相似查询复用
  + Agent conversation_history
  + Episodic/Procedural/Governed Memory
  + PG/Milvus/Kùzu 长期知识工具
  + Trace/Eval 质量闭环
```

短期记忆负责当前会话连续性，长期记忆负责芯片知识沉淀，语义缓存负责重复查询加速，Trace/评估负责可观测与质量改进。
