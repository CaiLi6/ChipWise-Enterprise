# Agent Tool Schema 工业级加固评估

## 1. 结论

当前 ChipWise Agent Tool Schema 属于**可用的工程级 schema**，但还不能算严格工业级。

综合评分：**6.5 / 10**

已经具备：

- 每个 Agent Tool 都暴露 `parameters_schema`。
- `ToolRegistry` 能转换为 OpenAI function-calling tools。
- 部分字段有 `required`、`enum`、`minItems`、`maxItems`。
- 高风险 SQL 工具有基础写操作拦截。
- 依赖型工具已通过手动注册注入真实依赖，避免空依赖工具暴露。

主要不足：

- 多数 schema 没有 `additionalProperties: false`。
- 缺少统一 runtime validation。
- 字符串长度、数组长度、数值范围、条件依赖不完整。
- 错误返回格式不统一。
- SQL/path/report/BOM 等高风险工具需要更严格安全边界。

## 2. 当前 Tool Schema 现状

代表性工具：

| Tool | 当前 schema 能力 | 主要缺口 |
|---|---|---|
| `rag_search` | `query` required，`doc_type` enum | `top_k` 无范围，`query/part_number` 无长度限制，无 `additionalProperties=false` |
| `graph_query` | `query_type` enum | 不同 `query_type` 的参数依赖未表达，`max_depth` 未在 schema 中声明 |
| `sql_query` | `sql` required，`params` array | SQL 安全仅正则拦截，缺少 SELECT-only parser、limit、timeout、只读 allowlist |
| `chip_compare` | `chip_names` min/max items | part number 格式未校验，dimensions 无 enum |
| `bom_review` | 支持 `file_path` 或 `bom_data` | 缺少 oneOf 条件约束，file path sandbox/大小/扩展名限制不足 |
| `design_rule` | `chip_name` required | 字符串长度/格式不足，内部异常有 silent pass |
| `report_export` | `format` enum | `data` schema 太宽，导出路径安全边界需加强 |
| `knowledge_search` | `query` required | `top_k` 无范围，`chip_id` 无 minimum |

## 3. 工业级 Tool Schema 标准

工业级 Agent Tool Schema 应满足：

1. **Schema 严格**
   - 所有 object 都有 `additionalProperties: false`。
   - 所有 string 有 `minLength/maxLength`。
   - 所有 number/integer 有 `minimum/maximum`。
   - 所有 enum 都显式列出。
   - 条件参数用 `oneOf` / `anyOf` / `dependentRequired` 表达。

2. **Runtime Validation**
   - 不只把 schema 给 LLM，还要在 `execute()` 前校验。
   - 校验失败返回统一错误结构。
   - 不允许工具自行 `kwargs.get()` 后静默默认危险值。

3. **安全边界**
   - SQL 只允许 SELECT/只读 CTE。
   - 自动追加或要求 LIMIT。
   - 文件路径限定 sandbox。
   - 报告导出路径限定 output directory。
   - 工具调用有 timeout 和最大输入大小。

4. **错误格式统一**
   - 建议统一：

```json
{
  "ok": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "top_k must be between 1 and 20",
    "details": {}
  }
}
```

成功返回：

```json
{
  "ok": true,
  "data": {},
  "citations": [],
  "meta": {}
}
```

5. **可观测**
   - 记录 tool name、arguments hash、validation result、duration、error code。
   - 对高风险工具记录审计日志。

## 4. 推荐改造方案

### Phase 1：Schema 严格化

目标：

- 给所有 tool schema 加 `additionalProperties: false`。
- 补齐 `minLength/maxLength/minimum/maximum`。
- 给 `top_k`、`chip_id`、`max_depth` 等加范围。
- 给 part number 加 pattern。

示例：

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "query": {
      "type": "string",
      "minLength": 1,
      "maxLength": 1000
    },
    "top_k": {
      "type": "integer",
      "minimum": 1,
      "maximum": 20,
      "default": 10
    }
  },
  "required": ["query"]
}
```

### Phase 2：Runtime validation

新增：

- `src/agent/tool_validation.py`
- `validate_tool_arguments(tool, kwargs)`
- `ToolValidationError`

在 `AgentOrchestrator._run_single_tool()` 中统一校验：

```text
tool_call args
  -> JSON Schema runtime validation
  -> normalized args
  -> tool.execute()
```

### Phase 3：高风险工具加固

SQL：

- 使用 SQL parser 或只读 allowlist。
- 禁止多语句。
- 禁止 `;`、DDL/DML、函数副作用。
- 强制 LIMIT。
- 参数必须使用 `$1/$2`。

文件：

- `file_path` 必须在允许目录内。
- 限制扩展名和文件大小。
- 禁止相对路径逃逸。

报告：

- 输出目录固定。
- 文件名 sanitize。
- 禁止覆盖系统路径。

### Phase 4：统一返回协议

所有工具统一返回：

```python
{
    "ok": True,
    "data": ...,
    "citations": [],
    "meta": {}
}
```

或：

```python
{
    "ok": False,
    "error": {
        "code": "...",
        "message": "...",
        "details": {}
    }
}
```

### Phase 5：测试与 CI

新增测试：

- 每个 tool schema 都能通过 JSON Schema metaschema。
- 每个 schema 都含 `additionalProperties: false`。
- invalid args 被统一拒绝。
- SQL 注入/写操作被拒绝。
- path traversal 被拒绝。
- top_k 超范围被拒绝。

## 5. 面试回答口径

如果面试官问“工具参数 schema 是否严格，是否工业级”，可以这样回答：

> 当前系统的 Tool Schema 已经具备工程可用性：每个工具都有 JSON Schema，支持 required、enum、数组长度等基础约束，并且 SQL 等高风险工具有基础安全拦截。但我不会把它称为严格工业级，因为工业级还需要 `additionalProperties=false`、完整的长度/范围/条件依赖、统一 runtime validation、高风险工具 sandbox 和统一错误协议。我的下一步规划是把工具参数定义迁移到 Pydantic/JSON Schema 双用模型，在 AgentOrchestrator 执行工具前统一校验，并对 SQL、文件路径、报告导出等工具增加 allowlist、timeout、limit 和审计日志。

## 6. 最终判断

当前状态：

```text
基础 Agent Tool Schema：完成
工程可用：完成
严格工业级：未完成
```

建议优先级：

1. 先做 `additionalProperties=false` 和 `top_k/字符串长度/数值范围`。
2. 再做统一 runtime validation。
3. 最后做 SQL/path/report 高风险工具安全加固。
