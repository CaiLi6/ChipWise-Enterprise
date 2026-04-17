# Chapter 1: Project Overview & Architecture

## Teaching Guide

### 1. Introduction (导入)

**Opening question**: "你知道半导体工程师日常查芯片资料有多痛苦吗？"

ChipWise Enterprise 解决的核心问题：
- 芯片 Datasheet 通常是几百页的 PDF，找一个参数要翻很久
- 不同厂商格式不统一，对比芯片需要手动开多个 PDF
- 技术知识散落在各处，新人上手慢

**Solution**: 自然语言提问 → 智能体自动查表、查图谱、做对比 → 返回精准答案 + 来源引用

### 2. Key Concepts (概念讲解)

#### 7-Layer Architecture

Draw this mental model:

```
┌─────────────────────────────────────────┐
│  Layer 1: Frontend (Gradio / Vue3)      │  ← 用户界面
├─────────────────────────────────────────┤
│  Layer 2: API Gateway (FastAPI :8080)   │  ← JWT + 限流 + 追踪
├─────────────────────────────────────────┤
│  Layer 3: Agent Orchestrator            │  ← ReAct 决策大脑
├─────────────────────────────────────────┤
│  Layer 4: Core Services                 │  ← 查询改写/对话/报告
├─────────────────────────────────────────┤
│  Layer 5: Model Services                │  ← LM Studio + BGE-M3 + Reranker
├─────────────────────────────────────────┤
│  Layer 6: Storage                       │  ← PG + Milvus + Redis + Kuzu
├─────────────────────────────────────────┤
│  Layer 7: Libs (Pluggable)              │  ← Factory 抽象层
└─────────────────────────────────────────┘
```

#### Agentic RAG vs Traditional RAG

| | Traditional RAG | ChipWise Agentic RAG |
|---|---|---|
| 决策 | 固定管线 | LLM 自主选择工具 |
| 工具 | 只有向量搜索 | 10 种工具（搜索/对比/图谱/SQL/...） |
| 迭代 | 一次检索 | 最多 5 轮 ReAct 迭代 |
| 图谱 | 无 | Kuzu 知识图谱增强排序 |

#### Local-First (零数据外泄)

所有推理在本地 AMD Ryzen AI 395 (128GB RAM) 上运行，通过 LM Studio 提供 OpenAI 兼容 API。**没有任何数据发送到外部服务器**。

### 3. Code Walkthrough (代码走读)

**Files to read** (in this order):

1. `CLAUDE.md` — Read the "Architecture (7 Layers)" table and "Online flow" description
2. `config/settings.yaml` — Skim the entire file to see all configurable components
3. `src/api/main.py` — See how the app is assembled (router registration, lifespan)

**Key points to highlight**:
- The online flow: `HTTP → JWT + rate limit → SemanticCache → ConversationManager → AgentOrchestrator → ResponseBuilder`
- How settings.yaml is the single source of truth for all behavior
- How `src/api/main.py` wires everything together

### 4. Hands-on Verification (动手验证)

```bash
# Show the project structure
ls src/

# Count source files per layer
find src/ -name "*.py" | head -30

# Read the main entry point
head -50 src/api/main.py
```

### 5. Quiz Questions

**Q1 (Concept)**: ChipWise 的 7 层架构中，哪一层负责决定"用哪个工具回答用户问题"？为什么这个决策不能硬编码？

**A1**: Layer 3 (Agent Orchestrator)。因为不同的查询需要不同的工具组合——型号对比需要 chip_compare 工具，参数查询需要 rag_search，设计规则需要 design_rule。硬编码无法处理这种灵活性。

**Q2 (Code reading)**: 在 `config/settings.yaml` 中，`llm.primary` 和 `llm.router` 有什么区别？为什么需要两个模型？

**A2**: primary (qwen3-35b) 用于复杂推理和生成最终答案，router (qwen3-1.7b) 用于轻量级任务如查询意图分类和工具选择。小模型响应更快、吞吐更高，用于不需要深度推理的路由决策。

**Q3 (Design)**: 如果公司要求所有数据必须走内网，不能连外网，ChipWise 的架构需要修改吗？

**A3**: 基本不需要修改。ChipWise 本身就是 local-first 设计——LM Studio 在本地运行，所有存储在本地 Docker 中。唯一可能需要调整的是 Celery 爬虫（crawler worker）不能爬外网，需要改为从内网文件服务器同步 Datasheet。
