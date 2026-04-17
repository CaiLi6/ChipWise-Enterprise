# Chapter 3: Agent Orchestrator (ReAct 智能体)

## Teaching Guide

### 1. Introduction

**Connect to Chapter 2**: "上一章我们看到 query router 把请求交给了 AgentOrchestrator。今天我们打开这个黑盒——看看 AI Agent 是怎么'思考'的。"

**Core question**: Agent 怎么知道该用哪个工具？如果第一次搜索结果不够好怎么办？

### 2. Key Concepts

#### ReAct Pattern

```
User Query: "STM32F407 的最大时钟频率是多少？"

Iteration 1:
  Thought: 用户问的是具体芯片参数，我需要搜索 datasheet
  Action: rag_search(query="STM32F407 max clock frequency")
  Observation: [找到 3 条相关结果，包含 168 MHz]

Iteration 2:
  Thought: 我已经找到答案了，可以直接回复
  Final Answer: STM32F407 的最大时钟频率是 168 MHz（来源: ST 官方 Datasheet, Page 23）
```

#### 10 Agent Tools

| Tool | Purpose | When Used |
|------|---------|-----------|
| `rag_search` | 语义混合检索 | 查参数、查资料 |
| `graph_query` | 知识图谱查询 | 查关系、查替代料 |
| `sql_query` | SQL 结构化查询 | 精确数值过滤 |
| `chip_compare` | 芯片对比 | 多芯片横向对比 |
| `chip_select` | 芯片选型 | 按需求推荐芯片 |
| `bom_review` | BOM 审查 | 供应链风险分析 |
| `test_case_gen` | 测试用例生成 | 生成验证测试 |
| `design_rule` | 设计规则检查 | 查 PCB/电气规则 |
| `knowledge_search` | 知识库检索 | 查用户笔记 |
| `report_export` | 报告导出 | 生成 PDF/Excel |

#### Auto-Discovery Mechanism

```python
# ToolRegistry.discover() does:
for module in src.agent.tools.*:
    for class in module:
        if issubclass(class, BaseTool) and not abstract:
            instance = class()
            registry[instance.name] = instance
```

Adding a new tool = just create a new `BaseTool` subclass. No registration code needed.

### 3. Code Walkthrough

**Files to read**:

1. `src/agent/tools/base_tool.py` — The ABC: name, description, parameters_schema, execute
2. `src/agent/tool_registry.py` — Auto-discovery logic (focus on `discover()` method)
3. `src/agent/orchestrator.py` — ReAct loop core
4. `src/agent/tools/rag_search.py` — The most used tool: hybrid → rerank → graph boost
5. `src/agent/token_budget.py` — Token budget tracking

**Key patterns**:
- `to_openai_tool()` — converts BaseTool to OpenAI function-calling JSON
- Token budget: 5 iterations max, 8192 tokens max
- Parallel tool calls: agent can call multiple tools in one iteration

### 4. Hands-on Verification

```bash
# List all tool files
ls src/agent/tools/

# Check what each tool is named
grep -r "def name" src/agent/tools/ --include="*.py"

# See the OpenAI schema generation
grep -A 5 "to_openai_tool" src/agent/tools/base_tool.py
```

### 5. Quiz Questions

**Q1 (Concept)**: ReAct 模式和传统的 Chain-of-Thought 有什么区别？为什么 ChipWise 选择 ReAct？

**A1**: Chain-of-Thought 只能推理然后一次性回答，不能与外部世界交互。ReAct 在推理（Thought）后可以执行动作（Action）并观察结果（Observation），然后继续推理。ChipWise 需要 Agent 能够搜索向量库、查图谱、做 SQL 查询——这些都是外部动作，只有 ReAct 能支持。

**Q2 (Code reading)**: `ToolRegistry.discover()` 中，如果一个 BaseTool 子类的 `__init__` 需要参数（如 RAGSearchTool 需要 hybrid_search），auto-discover 会怎样？

**A2**: `discover()` 用 `obj()` 无参构造，如果 `__init__` 需要参数会抛异常。代码 catch 了这个异常并 `continue` 跳过。这意味着需要依赖注入的工具（如 RAGSearchTool）不会被 auto-discover，需要手动注册。

**Q3 (Design)**: 如果要添加一个 "pin_mapping" 工具（查芯片引脚定义），你需要做什么？

**A3**: 1) 创建 `src/agent/tools/pin_mapping.py`，定义 `PinMappingTool(BaseTool)` 并实现 `name`、`description`、`parameters_schema`、`execute`。2) 如果不需要依赖注入，auto-discover 会自动注册。3) 如果需要依赖（比如数据库连接），需要在 orchestrator 初始化时手动注册。
