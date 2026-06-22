# 记忆系统面试回答稿

> 场景：面试官问“你的 Agent 记忆系统是如何设计的？”  
> 目标：用工程化语言说明设计理念、架构分层、运行链路、压缩机制、治理机制、技术取舍和可扩展点。

## 1. 一句话回答

我把记忆系统设计成了一个**分层 Agent Memory 架构**：用 Redis 承载短期会话记忆和语义缓存，用 PostgreSQL/Milvus/Kùzu 承载长期结构化、向量化和图谱化知识，用情节记忆和过程记忆沉淀每次查询经验，并通过 candidate/confirmed/rejected 的治理机制控制哪些记忆可以进入 Agent 上下文。

## 2. 设计出发点

我没有把所有对话历史直接塞进 prompt，而是按**生命周期、访问频率、可信度和数据结构**拆分记忆。

核心原因有三个：

1. **上下文窗口有限**：长对话、工具结果和 RAG chunk 很容易撑爆 prompt，所以必须压缩和筛选。
2. **不同记忆可信度不同**：datasheet 参数和用户偏好不能混在一起；长期事实必须来自可引用来源。
3. **不同数据访问模式不同**：短期会话需要低延迟，长期知识需要检索和治理，工具调用经验需要结构化沉淀。

所以我的设计原则是：

```text
短期记忆负责当前会话连续性；
长期知识负责事实来源；
情节记忆记录发生过什么；
过程记忆沉淀怎么做更好；
治理记忆决定哪些内容可以被长期使用；
所有记忆进入 prompt 前都要经过压缩、筛选和可信度控制。
```

## 3. 整体分层架构

整个记忆系统分成九层：

| 层级 | 名称 | 存储 | 作用 |
|---|---|---|---|
| L1 | Agent 工作记忆 | 单次请求内 messages | 当前推理上下文，包含 system prompt、当前 query、工具结果 |
| L2 | 短期会话记忆 | Redis `session:{user_key}:{session_id}` | 当前用户当前会话的 summary、turns、entities、pinned、checkpoints |
| L3 | 语义缓存记忆 | Redis `gptcache:bucket:{bucket}` | 相似 query 复用 answer/citations，降低重复 RAG/LLM 成本 |
| L4 | 长期结构化记忆 | PostgreSQL | 芯片参数、文档元数据、设计规则、errata、替代料等 |
| L5 | 长期向量记忆 | Milvus | datasheet chunks、knowledge notes 的语义检索 |
| L6 | 长期图谱记忆 | Kùzu | 芯片、参数、文档、替代料、errata 的多跳关系 |
| L7 | 情节记忆 | PostgreSQL `memory_episodes` | 每次查询的 query、tools、citations、grounding、outcome |
| L8 | 过程记忆 | PostgreSQL `memory_procedures` | 某类问题适合什么工具链的经验 |
| L9 | 治理记忆 | PostgreSQL `memory_records` | user/project 级可控记忆，支持 candidate/confirmed/rejected |

前端还有一层 localStorage 记忆，用来保存浏览器侧多会话 UI 和 token 状态，但我不会把它作为后端可信上下文来源。

## 4. 在线查询时记忆如何运行

一次用户查询的完整链路是：

```text
用户提问
  -> JWT 鉴权，得到 user_key
  -> 校验 session_id
  -> 从 Redis 加载短期会话记忆
  -> MemoryRetriever 按预算选择相关 summary / pinned / turns
  -> QueryRewriter 基于历史做指代消解
  -> 加载 confirmed user/project 治理记忆
  -> 加载过程记忆 procedural hints
  -> 查 SemanticCache
      -> cache hit：直接返回缓存答案，并写 episode
      -> cache miss：进入 AgentOrchestrator
  -> Agent 调用 sql_query / rag_search / graph_query 等工具
  -> 工具读取 PostgreSQL / Milvus / Kùzu 长期知识
  -> grounding 校验答案和 citations
  -> 写回 Redis 短期会话
  -> 写入 memory_episodes 情节记忆
  -> 更新 memory_procedures 过程记忆
  -> 捕获用户显式“记住”内容到 confirmed user memory
  -> 高质量 episode 生成 candidate project memory
  -> 返回答案
```

这个链路的重点是：**记忆不是无脑注入 prompt，而是先检索、压缩、筛选，再作为辅助上下文进入 Agent。**

## 5. 短期会话记忆如何设计

短期记忆存 Redis，key 是：

```text
session:{user_key}:{session_id}
```

payload 是 versioned JSON：

```json
{
  "version": 2,
  "summary": "压缩后的会话摘要",
  "turns": [
    {
      "role": "user",
      "content": "PH2A106FLG900 的 DSP 数量是多少？",
      "created_at": 1710000000.0,
      "metadata": {
        "importance": 0.78,
        "topics": ["parameter_query"],
        "entities": {"chips": ["PH2A106FLG900"]},
        "facts": []
      }
    }
  ],
  "entities": {"chips": ["PH2A106FLG900"]},
  "pinned": [],
  "checkpoints": [],
  "updated_at": 1710000001.0
}
```

这里我做了几个设计：

1. **version 字段**：便于旧格式迁移和后续升级。
2. **summary**：压缩后的旧上下文，不保留完整长历史。
3. **turns**：最近若干轮原始消息。
4. **metadata**：每条 turn 的重要性、主题、实体和事实片段。
5. **pinned**：用户显式要求记住或高重要性的内容，压缩时不丢。
6. **checkpoints**：每次 compact 生成的历史压缩点，便于回溯。

## 6. 压缩机制如何设计

压缩机制参考了 Claude Code 的 compact 思路，但做了适配。

我没有只按“保留最近 N 条”来截断，而是做了 **checkpoint-based compaction**。

触发条件有两个：

1. `turns` 数量超过 `compression_threshold`；
2. `summary + turns` 估算字符数超过 `compaction_budget_chars`。

触发后流程是：

```text
turns
  -> 识别 pinned turns
  -> old_turns 压缩成结构化 summary
  -> 生成 checkpoint
  -> 保留 recent turns
  -> 保存 summary + pinned + checkpoints + recent turns
```

摘要不是一段自然语言，而是结构化分区：

- 当前目标
- 已确认事实
- 用户偏好
- 关键实体
- 工具证据
- 未完成问题
- 下一步

这样做的好处是：

1. **不会无限增长**：旧上下文被压进 summary。
2. **不会丢关键偏好**：pinned memory 单独保护。
3. **可回溯**：checkpoints 保存每次 compact 的摘要和压缩规模。
4. **更抗幻觉**：数字和参数必须来自 facts 或工具证据，不能随便写进摘要。

## 7. MemoryRetriever 如何控制 prompt

即使 Redis 中有 summary、turns、pinned，也不会全部进入 prompt。

我设计了 MemoryRetriever：

```text
query + ConversationContext
  -> 计算相关性
  -> 保留 summary
  -> 保留 pinned memory
  -> 按 query 相关性选择 turns
  -> 受 prompt_budget_chars 限制
```

相关性主要考虑：

- 当前 query 和历史 turn 的关键词重合；
- 芯片实体是否一致；
- turn 的 importance；
- 是否属于最近 `recent_turns_always` 条消息。

这样做可以避免长会话中无关历史污染当前问题。

## 8. 长期知识记忆如何设计

长期知识没有直接放进会话记忆，而是分三种存储：

### PostgreSQL

存结构化事实：

- `chips`
- `chip_parameters`
- `documents`
- `design_rules`
- `errata`
- `chip_alternatives`

适合精确查询，比如：

```text
PH2A106FLG900 的 DSP 数量是多少？
```

这种问题优先走 `sql_query`。

### Milvus

存 datasheet chunks 和 knowledge notes 的向量。

适合语义检索，比如：

```text
PH2A106FLG900 和 XCKU5PFFVD900 的 PCIe 兼容性有什么差异？
```

这种问题走 `rag_search`。

### Kùzu

存图谱关系：

- Chip -> Parameter
- Chip -> Document
- Chip -> Errata
- Chip -> Alternative
- Chip -> DesignRule

适合关系问题、替代料问题、多跳推理。

## 9. 情节记忆如何设计

每次查询都会写入一条 episode：

```json
{
  "query_text": "PH2A106FLG900 的 DSP 数量是多少？",
  "rewritten_query": "PH2A106FLG900 的 DSP 数量是多少？",
  "tools_used": ["sql_query"],
  "citations": [],
  "grounding": {"coverage": 1.0},
  "outcome": "success"
}
```

它的作用不是直接回答问题，而是用于：

1. 查询回放；
2. 失败分析；
3. 评估统计；
4. 过程记忆学习；
5. 生成 candidate memory。

## 10. 过程记忆如何设计

过程记忆解决的是：**以后遇到类似问题，该优先用什么工具链？**

比如：

```json
{
  "intent": "single_numeric_parameter",
  "trigger_patterns": ["主频", "DSP", "IO", "PCIe"],
  "recommended_tools": ["sql_query", "rag_search"],
  "stop_rules": ["SQL 命中明确参数后直接回答"]
}
```

我内置了几类保守策略：

1. 单参数/数值问题：优先 SQL；
2. 替代/兼容关系：优先图谱；
3. 设计规则/errata：优先 RAG。

成功 episode 会更新 procedure 的 success_count，失败会更新 failure_count。

但过程记忆只是 hint，不会绕过 grounding，也不会覆盖真实数据源。

## 11. 治理记忆如何设计

治理记忆是 user/project 级长期可控记忆，存 `memory_records`。

它有状态机：

```text
candidate -> confirmed -> rejected/deleted
```

只有 `confirmed` 的记忆才会进入 prompt。

来源包括：

1. 用户显式说“记住…”；
2. 系统从高质量 episode 中提取 candidate；
3. 用户或管理员手动创建；
4. 后续可以从评估结果中自动提出候选。

这样可以解决记忆污染问题：**系统可以建议记住，但不能默认永久相信。**

## 12. 为什么不把所有记忆放 PostgreSQL

因为不同记忆的访问模式不同：

| 数据 | 最适合存储 | 原因 |
|---|---|---|
| 当前会话 turns | Redis | 低延迟、TTL、频繁读写 |
| 相似查询缓存 | Redis | 快速命中、可过期 |
| 芯片参数 | PostgreSQL | 结构化、可查询、事务一致 |
| 文档 chunk | Milvus | 向量检索 |
| 芯片关系 | Kùzu | 图遍历 |
| 查询 episode | PostgreSQL | 结构化分析、统计 |
| trace/eval | JSONL | append-only、低侵入 |
| 前端会话 UI | localStorage | 浏览器体验 |

所以这不是“数据库越统一越好”，而是按数据特性分层。

## 13. 如何防止记忆污染

我主要做了五层保护：

1. **grounding**：最终答案必须基于 citations 和数字对齐。
2. **candidate 状态**：自动生成的 project memory 默认不进入 prompt。
3. **confirmed 才注入**：只有确认过的治理记忆会被使用。
4. **pinned 保护但不越权**：pinned 保存偏好和任务状态，不覆盖 datasheet 事实。
5. **长期知识优先**：PG/Milvus/Kùzu 的真实来源优先于历史对话。

## 14. 这个设计的取舍

优点：

- 支持多轮上下文恢复；
- 支持长会话压缩；
- 支持工具策略学习；
- 支持用户可控记忆；
- 支持低幻觉检索；
- 支持后续评估闭环。

代价：

- 系统复杂度更高；
- 需要维护 Redis、PG、Milvus、Kùzu 多存储；
- 需要治理机制避免记忆污染；
- 需要评估验证记忆是否真的提升效果。

## 15. 面试总结版

如果面试官让我总结，我会说：

> 我设计的记忆系统不是简单保存聊天历史，而是一个分层 Agent Memory 架构。短期会话记忆放 Redis，并通过 checkpoint compaction、pinned memory 和 prompt budget 控制上下文；长期领域知识放 PostgreSQL、Milvus 和 Kùzu，分别支持结构化查询、语义检索和图谱推理；每次查询还会沉淀为 episode，并进一步学习 procedure hints；用户和项目级记忆通过 candidate/confirmed/rejected 状态治理，只有 confirmed memory 才能进入 prompt。整体目标是让 Agent 既能多轮连续对话，又能从历史经验中学习，同时避免记忆污染和幻觉扩散。

