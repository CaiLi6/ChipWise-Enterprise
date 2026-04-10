# 6. 项目排期

## 6.1 开发排期总览

```
Phase 1 ──── Phase 2 ──── Phase 3 ──── Phase 4 ──── Phase 5 ──── Phase 6
基础设施      核心RAG       数据工程      结构化管线    高级功能      前端+交付
Week 1-2     Week 3-4     Week 5-7     Week 8-10    Week 11-13   Week 14-16
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## 6.2 分阶段计划概览

| Phase | 时间 | 目标 | 任务数 |
|-------|------|------|--------|
| **Phase 1: 基础设施** | Week 1-2 | Docker 可启动 → 数据库可连 → API 可响应 | 18 |
| **Phase 2: 核心 RAG** | Week 3-4 | Libs 可插拔层 + Graph RAG + Agent 端到端可用 | 19 |
| **Phase 3: 数据工程** | Week 5-7 | 完整 Ingestion 流水线 + 三路数据采集 | 13 |
| **Phase 4: 结构化管线** | Week 8-10 | 芯片对比 / 选型 / BOM 审查三个核心 Tool | 8 |
| **Phase 5: 高级功能** | Week 11-13 | 测试用例 / 设计规则 / 知识沉淀 / 报告导出 | 9 |
| **Phase 6: 前端+交付** | Week 14-16 | Gradio MVP + SSO + Prometheus/Grafana + E2E + 安全测试 + 负载测试 | 11 |

> **详细任务排期、验收标准和测试方法请参考 [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md)**

## 6.3 开发规范 SOP

### 分支策略

```
main ─────────────────────────────────────────────── (稳定发布)
  └── develop ────────────────────────────────────── (开发集成)
        ├── feature/phase1-infra
        ├── feature/phase2-rag
        ├── feature/phase3-ingestion
        └── ...
```

### 提交与合并规范

- **Commit Message**: `<type>(<scope>): <description>` (e.g., `feat(pipeline): add chip comparison pipeline`)
- **PR 合并**: 至少 1 人 Code Review + CI 通过
- **CI Pipeline**: lint (ruff) → type check (mypy) → unit tests → integration tests

---


---

> 以下为 `docs/DEVELOPMENT_PLAN.md` 完整内容（详细任务排期）

# ChipWise Enterprise — Development Plan

> 本文档从 `ENTERPRISE_DEV_SPEC.md` v5.0 中提取的详细开发任务排期。
> 包含各阶段的任务分解、验收标准和测试方法。
> 架构设计详情请参考 [ENTERPRISE_DEV_SPEC.md](./ENTERPRISE_DEV_SPEC.md)。
> **注意**: 所有 `§` 章节引用对齐 ENTERPRISE_DEV_SPEC.md v5.0（2026-04-09 更新，含 §2.9-2.11 新增章节、§3/§5.7 Phase X 标注、§5.2 扩展指标）。

> **排期原则（严格对齐 ENTERPRISE_DEV_SPEC v5.0 架构分层与 §4.4 目录结构）**
>
> - **只按 DEV_SPEC 设计落地**：以 §4.4 目录树为"交付清单"，每一步都在文件系统上产生可见变化。
> - **Phase 层层递进**：Phase 1 基建 → Phase 2 核心能力 → Phase 3 数据工程 → Phase 4 业务 Tool → Phase 5 高级特性 → Phase 6 前端与交付。后阶段依赖前阶段产出。
> - **外部依赖可替换/可 Mock**：LLM/Embedding/VectorStore/GraphStore/Reranker 真实调用在单元测试中一律用 Fake/Mock，集成测试再开真实后端（可选）。
> - **每个任务有验收标准 + 测试方法**：TDD 驱动，先写测试再实现。
> - **可插拔架构优先**：所有后端组件通过 Factory + Base 抽象，切换实现只改 `config/settings.yaml`。

### 阶段总览（大阶段 → 目的）

| Phase | 名称 | 目的 | 任务数 |
|-------|------|------|--------|
| **Phase 1** | Infrastructure & Skeleton | 工程骨架 + Docker 基建 + 模型服务 + API 网关 + 图谱骨架 | 18 |
| **Phase 2** | Agentic RAG + Graph RAG Core | Libs 可插拔层 + 检索 + Agent 框架 + Core 服务 | 19 |
| **Phase 3** | Data Engineering Pipeline | PDF 解析 + Celery 异步链 + 三路数据采集 | 13 |
| **Phase 4** | Structured Query Tools | 芯片对比 / 选型 / BOM 审查三个核心 Tool | 8 |
| **Phase 5** | Advanced Features | 测试用例 / 设计规则 / 知识沉淀 / 报告导出四组高级 Tool | 9 |
| **Phase 6** | Frontend & Delivery | Gradio 前端 + SSO + Prometheus/Grafana + 压测 + E2E 验收 + 文档 | 11 |
| **总计** | | | **78** |

---

### 📊 进度跟踪表 (Progress Tracking)

> **状态说明**：`[ ]` 未开始 | `[~]` 进行中 | `[x]` 已完成
>
> **更新时间**：每完成一个子任务后更新对应状态

#### Phase 1：Infrastructure & Skeleton

##### 子阶段 1A：工程骨架与测试基座

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 1A1 | 初始化企业级目录树与最小可运行入口 | [x] | 2026-04-10 | |
| 1A2 | 引入 pytest 并建立测试目录约定 | [x] | 2026-04-10 | |
| 1A3 | Settings 配置加载与校验（适配新后端） | [x] | 2026-04-10 | |

##### 子阶段 1B：Docker 基础设施

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 1B1 | Docker Compose 基础设施编排 (PG/Milvus/Redis) | [x] | 2026-04-10 | |
| 1B2 | PostgreSQL Schema 初始化 (Alembic) | [x] | 2026-04-10 | |
| 1B3 | Milvus Collection 与索引创建 | [x] | 2026-04-10 | |
| 1B4 | 基础设施健康检查脚本 | [x] | 2026-04-10 | |

##### 子阶段 1C：模型微服务

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 1C1 | BGE-M3 Embedding FastAPI 微服务 | [x] | 2026-04-10 | |
| 1C2 | bce-reranker FastAPI 微服务 | [x] | 2026-04-10 | |
| 1C3 | LM Studio 安装与验证 | [x] | 2026-04-10 | |

##### 子阶段 1D：FastAPI Gateway 基建

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 1D1 | FastAPI App 骨架 + Health/Readiness 端点 | [x] | 2026-04-10 | |
| 1D2 | DI 容器 (dependencies.py) | [x] | 2026-04-10 | |
| 1D3 | JWT Auth 中间件 (RS256) | [x] | 2026-04-10 | |
| 1D4 | Rate Limiter 中间件 (Redis Token Bucket) | [x] | 2026-04-10 | |
| 1D5 | Request Logger 中间件 | [x] | 2026-04-10 | |

##### 子阶段 1E：Kùzu 图谱 + Agent 骨架

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 1E1 | Kùzu 图数据库初始化脚本 (6 节点表 + 7 关系表) | [x] | 2026-04-10 | |
| 1E2 | BaseGraphStore 抽象接口 + KuzuGraphStore 实现 | [x] | 2026-04-10 | |
| 1E3 | Agent Orchestrator 骨架 + BaseTool + ToolRegistry | [x] | 2026-04-10 | |

#### Phase 2：Agentic RAG + Graph RAG Core

##### 子阶段 2A：Libs 可插拔层

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 2A1 | MilvusStore (BaseVectorStore 实现) | [x] | 2026-04-10 | |
| 2A2 | BGE-M3 Client (BaseEmbedding 实现) | [x] | 2026-04-10 | |
| 2A3 | bce-reranker Client (BaseReranker 实现) | [x] | 2026-04-10 | |
| 2A4 | LMStudio LLM Client (BaseLLM 实现) | [x] | 2026-04-10 | |
| 2A5 | BaseGraphStore + KuzuGraphStore + GraphStoreFactory | [x] | 2026-04-10 | |
| 2A6 | Kùzu Schema 初始化脚本 | [ ] | | |

##### 子阶段 2B：Retrieval 检索层

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 2B1 | Milvus 原生 Hybrid Search (Dense+Sparse+RRF) | [ ] | | |
| 2B2 | Graph Search (Kùzu Cypher 查询封装) | [ ] | | |
| 2B3 | Reranker 编排 (bce-reranker 远程调用 + Fallback) | [ ] | | |
| 2B4 | 多路结果融合 (fusion.py) | [ ] | | |

##### 子阶段 2C：Agent 框架

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 2C1 | BaseTool + ToolRegistry 自动发现 | [ ] | | |
| 2C2 | AgentOrchestrator ReAct 主循环 | [ ] | | |
| 2C3 | TokenBudget + SafetyGuardrails + Structured Output Validator | [ ] | | |
| 2C4 | rag_search Tool (Hybrid + Graph Boost) | [ ] | | |
| 2C5 | graph_query Tool (4 种图查询) | [ ] | | |
| 2C6 | sql_query Tool (参数化 PG 查询) | [ ] | | |

##### 子阶段 2D：Core 服务层

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 2D1 | ConversationManager (Redis Session) | [ ] | | |
| 2D2 | QueryRewriter (LLM 代词消解) | [ ] | | |
| 2D3 | GPTCache 语义缓存 | [ ] | | |

#### Phase 3：Data Engineering Pipeline

##### 子阶段 3A：PDF 解析与结构化提取

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 3A1 | PDF 三级表格提取 (pdfplumber→Camelot→PaddleOCR) | [ ] | | |
| 3A2 | LLM 结构化参数抽取 (表格→JSON→PG) | [ ] | | |
| 3A3 | Datasheet 感知分片器 | [ ] | | |
| 3A4 | 表格专用分片器 (table_chunker) | [ ] | | |

##### 子阶段 3B：Celery 异步任务链

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 3B1 | Celery 基座 + 配置 + Worker 启动 | [ ] | | |
| 3B2 | Ingestion 单步 Tasks (download→dedup→extract→chunk→embed→store) | [ ] | | |
| 3B3 | Graph Sync Task (PG→Kùzu 增量同步) | [ ] | | |
| 3B4 | Task Chain 编排 + 优先级队列 | [ ] | | |
| 3B5 | 任务进度 WebSocket 推送 | [ ] | | |

##### 子阶段 3C：数据采集三路

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 3C1 | 手动上传 API (POST /api/v1/documents/upload) | [ ] | | |
| 3C2 | Watchdog 内网目录监听 | [ ] | | |
| 3C3 | Playwright 定时爬虫 (ST/TI/NXP) | [ ] | | |
| 3C4 | DocumentManager 跨存储协调删除 | [ ] | | |

#### Phase 4：Structured Query Tools

##### 子阶段 4A：芯片对比 Tool

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 4A1 | chip_compare Tool (SQL 参数对比 + LLM 分析) | [ ] | | |
| 4A2 | 芯片对比 API 端点 (POST /api/v1/compare) | [ ] | | |

##### 子阶段 4B：选型推荐 Tool

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 4B1 | chip_select Tool (结构化过滤 + 语义排序) | [ ] | | |
| 4B2 | 国产替代匹配 (chip_alternatives 集成) | [ ] | | |
| 4B3 | chip_alternatives 数据填充脚本 | [ ] | | |

##### 子阶段 4C：BOM 审查 Tool

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 4C1 | bom_review Tool (Excel 解析 + 型号匹配) | [ ] | | |
| 4C2 | EOL/NRND 检测 + 参数冲突检测 | [ ] | | |
| 4C3 | 替代料自动推荐 | [ ] | | |

#### Phase 5：Advanced Features

##### 子阶段 5A：测试用例生成

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 5A1 | test_case_gen Tool (参数 → LLM 生成测试项) | [ ] | | |
| 5A2 | Excel/CSV 导出引擎 | [ ] | | |

##### 子阶段 5B：设计规则检查

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 5B1 | design_rule_check Tool (规则 + Errata + App Note) | [ ] | | |
| 5B2 | 设计规则自动提取 (Ingestion 阶段扩展) | [ ] | | |
| 5B3 | Errata 文档解析与数据填充 | [ ] | | |

##### 子阶段 5C：知识沉淀

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 5C1 | Knowledge Notes CRUD API + Milvus 向量化 | [ ] | | |
| 5C2 | knowledge_search Tool (团队心得纳入 RAG 检索) | [ ] | | |

##### 子阶段 5D：报告导出

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 5D1 | ReportEngine (Word/PDF/Excel 生成) | [ ] | | |
| 5D2 | report_export Tool (Agent 可调用的报告导出) | [ ] | | |

#### Phase 6：Frontend & Delivery

##### 子阶段 6A：Gradio MVP 前端

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 6A1 | Gradio 对话界面 + 文档上传 + 对比展示 | [ ] | | |
| 6A2 | SSE 流式输出 (LLM 生成实时展示) | [ ] | | |
| 6A3 | 监控仪表盘 (系统状态 + 请求统计 + Token 追踪) | [ ] | | |
| 6A4 | Prometheus + Grafana Docker 部署 | [ ] | | |

##### 子阶段 6B：SSO/OIDC 集成

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 6B1 | SSO Provider 适配器 (Keycloak + 钉钉 + 飞书) | [ ] | | |
| 6B2 | OIDC 中间件 + JIT Provisioning + 本地降级 | [ ] | | |

##### 子阶段 6C：压测 + 安全审计

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 6C1 | Locust 20 人并发压测 | [ ] | | |
| 6C2 | OWASP Top 10 安全审计 + GitHub Code Scanning | [ ] | | |

##### 子阶段 6D：E2E 验收 + 文档

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| 6D1 | 全部 10 个 Agent Tools E2E 测试 | [ ] | | |
| 6D2 | 部署运维文档 | [ ] | | |
| 6D3 | 用户使用手册 + README 完善 | [ ] | | |

### 📈 总体进度

| Phase | 总任务数 | 已完成 | 进度 |
|-------|---------|--------|------|
| Phase 1 | 18 | 18 | 100% |
| Phase 2 | 19 | 5 | 26% |
| Phase 3 | 13 | 0 | 0% |
| Phase 4 | 8 | 0 | 0% |
| Phase 5 | 9 | 0 | 0% |
| Phase 6 | 11 | 0 | 0% |
| **总计** | **78** | **23** | **29%** |

---

### Phase 1: Infrastructure & Skeleton (Week 1-2)

**目标**: 企业级工程骨架、Docker 基础设施、模型微服务就绪、FastAPI 网关基建、Kùzu 图谱与 Agent 骨架。

> **排期原则**
>
> - **先目录骨架与测试基座，再 Docker 基建，再模型微服务，再 API 网关，最后图谱 + Agent 骨架**。
> - PG/Milvus/Redis 先 Docker 跑通，再写 Python 初始化脚本。
> - BGE-M3 和 bce-reranker 在 Docker 单独部署为微服务（:8001, :8002）。
> - LM Studio 手动安装并加载模型（:1234），提供 OpenAI 兼容 API。

#### Phase 1 子阶段总览

| 子阶段 | 目的 | 任务数 |
|--------|------|--------|
| **1A: 工程骨架与测试基座** | 目录树 + pytest + Settings | 3 |
| **1B: Docker 基础设施** | PG/Milvus/Redis 编排 + Schema 初始化 | 4 |
| **1C: 模型微服务** | BGE-M3 :8001 + bce-reranker :8002 + LM Studio | 3 |
| **1D: FastAPI Gateway 基建** | App 骨架 + Auth + Rate Limit + Logger | 5 |
| **1E: Kùzu 图谱 + Agent 骨架** | Kùzu 初始化 + GraphStore + Agent 骨架 | 3 |
| **合计** | | **18** |

---

### 1A1：初始化企业级目录树与最小可运行入口
- **目标**：在 repo 根目录创建 §4.4 所述企业级目录骨架与空模块文件（可 import）。
- **修改/创建文件**：
  - `pyproject.toml`（项目元数据、依赖声明）
  - `requirements.txt`（核心依赖锁定）
  - `requirements-services.txt`（模型微服务依赖：sentence-transformers、FlagEmbedding 等）
  - `README.md`（最小项目说明）
  - `.gitignore`（Python 项目标准忽略 + `__pycache__`、`.venv`、`.env`、`*.pyc`、`logs/`、`data/`）
  - `src/__init__.py`
  - `src/api/__init__.py`
  - `src/api/main.py`（空 FastAPI app 占位）
  - `src/api/dependencies.py`（空 DI 占位）
  - `src/api/middleware/__init__.py`
  - `src/api/routers/__init__.py`
  - `src/api/schemas/__init__.py`
  - `src/core/__init__.py`
  - `src/core/settings.py`（占位）
  - `src/core/types.py`（占位）
  - `src/agent/__init__.py`
  - `src/agent/tools/__init__.py`
  - `src/agent/safety/__init__.py`
  - `src/pipelines/__init__.py`
  - `src/ingestion/__init__.py`
  - `src/ingestion/chunking/__init__.py`
  - `src/retrieval/__init__.py`
  - `src/cache/__init__.py`
  - `src/libs/__init__.py`
  - `src/libs/llm/__init__.py`
  - `src/libs/embedding/__init__.py`
  - `src/libs/vector_store/__init__.py`
  - `src/libs/graph_store/__init__.py`
  - `src/libs/reranker/__init__.py`
  - `src/libs/loader/__init__.py`
  - `src/services/__init__.py`
  - `src/observability/__init__.py`
  - `src/observability/logger.py`（占位：提供 `get_logger()`，stderr 输出）
  - `config/settings.yaml`（最小可解析企业级配置，包含 llm/embedding/reranker/vector_store/graph_store/agent/pg/redis/auth 段）
  - `config/prompts/`（空目录占位）
  - `scripts/__init__.py`
  - `data/documents/`（空目录占位）
  - `logs/`（空目录占位）
- **实现类/函数**：无（仅骨架，不实现业务逻辑）。
- **验收标准**：
  - 目录结构与 ENTERPRISE_DEV_SPEC §4.4 一致（至少顶层包全部存在）。
  - 能导入关键顶层包：
    ```bash
    python -c "import src.api; import src.core; import src.agent; import src.pipelines; import src.ingestion; import src.retrieval; import src.libs; import src.services; import src.observability; import src.cache"
    ```
  - `config/settings.yaml` 可被 `yaml.safe_load()` 正常解析。
- **测试方法**：`python -m compileall src`（仅做语法/可导入性检查；pytest 基座在 1A2 建立）。

---

### 1A2：引入 pytest 并建立测试目录约定
- **目标**：建立 `tests/unit|integration|e2e|load|fixtures` 目录与 pytest 运行基座。
- **修改/创建文件**：
  - `pyproject.toml`（添加 `[tool.pytest.ini_options]`：testpaths、markers `unit/integration/e2e/load`、asyncio_mode）
  - `tests/__init__.py`
  - `tests/conftest.py`（全局 fixtures 占位：`settings_override`、`tmp_data_dir`）
  - `tests/unit/__init__.py`
  - `tests/unit/test_smoke_imports.py`（冒烟测试：导入所有顶层包）
  - `tests/integration/__init__.py`
  - `tests/e2e/__init__.py`
  - `tests/load/__init__.py`
  - `tests/fixtures/`（放 1 个最小 `sample.pdf` 占位文件）
- **实现类/函数**：无（新增的是测试文件与 pytest 配置）。
- **验收标准**：
  - `pytest -q` 可运行并全部通过。
  - 至少 1 个冒烟测试通过（`test_smoke_imports.py` 验证所有顶层包可 import）。
  - markers 正确注册：`pytest --markers` 能看到 `unit`、`integration`、`e2e`、`load`。
- **测试方法**：`pytest -q tests/unit/test_smoke_imports.py`

---

### 1A3：Settings 配置加载与校验（适配新后端）
- **目标**：实现读取 `config/settings.yaml` 的配置加载器，适配企业级后端（PG/Milvus/Redis/LM Studio/BGE-M3/bce-reranker），启动时校验关键字段存在。
- **修改/创建文件**：
  - `src/core/settings.py`（集中放 Settings 数据结构与加载/校验逻辑）
  - `src/observability/logger.py`（补齐：`get_logger(name) -> logging.Logger`，JSON 格式 stderr 输出）
  - `config/settings.yaml`（补齐企业级字段：llm/embedding/reranker/vector_store/graph_store/agent/database/redis/auth/celery/observability）
  - `tests/unit/test_settings.py`
  - `tests/fixtures/settings_valid.yaml`（合法配置样例）
  - `tests/fixtures/settings_missing_field.yaml`（缺失关键字段的配置样例）
- **实现类/函数**：
  - `Settings`（Pydantic BaseModel 或 dataclass）：
    - 子结构：`LLMSettings`、`EmbeddingSettings`、`RerankerSettings`、`VectorStoreSettings`、`GraphStoreSettings`、`AgentSettings`、`DatabaseSettings`、`RedisSettings`、`AuthSettings`、`CelerySettings`、`ObservabilitySettings`
  - `load_settings(path: str = "config/settings.yaml") -> Settings`（读取 YAML → 解析为 Settings → 校验必填字段）
  - `validate_settings(settings: Settings) -> None`（集中化必填字段检查，错误信息包含字段路径，例如 `embedding.base_url`）
- **验收标准**：
  - `load_settings()` 能成功加载 `config/settings.yaml` 并返回 `Settings` 对象。
  - 所有企业级子配置段均可访问（如 `settings.database.host`、`settings.redis.url`、`settings.auth.sso.provider`）。
  - 删除/缺失关键字段时（例如 `vector_store.backend`），`load_settings()` 抛出明确错误（指出缺的是哪个字段路径）。
  - 环境变量可覆盖敏感字段（如 `PG_PASSWORD`、`REDIS_URL`、`JWT_SECRET_KEY`）。
- **测试方法**：`pytest -q tests/unit/test_settings.py`

---

### 1B1：Docker Compose 基础设施编排 (PG/Milvus/Redis)
- **目标**：编写 `docker-compose.yml`，一键拉起 PostgreSQL 15 + Milvus Standalone + Redis 7，三个服务均带 healthcheck。
- **修改/创建文件**：
  - `docker-compose.yml`（基础设施层，内容严格对齐 §4.5.2 定义）
  - `.env.example`（环境变量模板：`PG_PASSWORD`、`POSTGRES_DB`、`REDIS_MAXMEMORY` 等）
  - `tests/integration/test_docker_infra_health.py`
- **实现类/函数**：无（纯 YAML 编排 + 测试脚本）。
- **验收标准**：
  - `docker-compose up -d` 后，三个容器全部 `healthy`：
    - PostgreSQL：`pg_isready -U chipwise` 返回成功
    - Milvus：`curl -f http://localhost:9091/healthz` 返回 200
    - Redis：`redis-cli ping` 返回 `PONG`
  - 资源限制与 §4.5.2 一致（PG 4G / Milvus 16G / Redis 3G）。
  - 数据卷正确持久化（`pg_data`、`milvus_data`、`redis_data`）。
- **测试方法**：`pytest -q tests/integration/test_docker_infra_health.py -m integration`（需 Docker 运行环境）

---

### 1B2：PostgreSQL Schema 初始化 (Alembic)
- **目标**：使用 Alembic 管理 PostgreSQL 迁移，创建 §4.7.1 中定义的全部 12 张表及索引。
- **前置条件**：1B1 Docker PostgreSQL 容器运行中。
- **修改/创建文件**：
  - `alembic.ini`（Alembic 主配置，`sqlalchemy.url` 从环境变量读取）
  - `alembic/env.py`（迁移环境配置）
  - `alembic/versions/001_initial_schema.py`（初始迁移：12 张表 + 全部索引）
  - `scripts/init_db.py`（一键初始化脚本：创建 DB → 执行 Alembic migrate → 验证表存在）
  - `tests/integration/test_pg_schema.py`
- **实现类/函数**：
  - `scripts/init_db.py`：
    - `init_database(db_url: str) -> None`（执行 Alembic upgrade head）
    - `verify_schema(db_url: str) -> bool`（检查 12 张表全部存在）
  - Alembic migration 中的 DDL 严格对齐 §4.7.1（chips / chip_parameters / documents / document_images / users / bom_records / bom_items / knowledge_notes / chip_alternatives / design_rules / errata / query_audit_log）
- **验收标准**：
  - `alembic upgrade head` 无报错，12 张表全部创建成功。
  - `python scripts/init_db.py` 能幂等执行（重复运行不报错）。
  - 关键索引存在：`idx_chips_part_number`、`idx_params_chip_name`、`idx_documents_hash`、`idx_notes_tags` (GIN)。
  - `alembic downgrade base` 能干净回滚。
- **测试方法**：`pytest -q tests/integration/test_pg_schema.py -m integration`

---

### 1B3：Milvus Collection 与索引创建
- **目标**：编写脚本创建 §4.7.2 定义的两个 Collection（`datasheet_chunks` + `knowledge_notes`）及 §4.7.2 的 HNSW/Sparse 索引。
- **前置条件**：1B1 Docker Milvus 容器运行中。
- **修改/创建文件**：
  - `scripts/init_milvus.py`（Collection 创建 + 索引构建脚本）
  - `tests/integration/test_milvus_collections.py`
- **实现类/函数**：
  - `scripts/init_milvus.py`：
    - `create_collections(host: str, port: int) -> None`（创建 `datasheet_chunks` 和 `knowledge_notes` Collection）
    - `create_indexes(collection: Collection) -> None`（为 dense_vector 创建 HNSW 索引 `M=16, efConstruction=256`；为 sparse_vector 创建 `SPARSE_INVERTED_INDEX`）
    - `verify_collections(host: str, port: int) -> bool`（验证两个 Collection 存在且索引 Ready）
  - Schema 严格对齐 §4.7.2：`chunk_id(PK)`, `dense_vector(1024-dim)`, `sparse_vector`, `chip_id`, `part_number`, `manufacturer`, `doc_type`, `page`, `section`, `content`, `collection`
- **验收标准**：
  - 脚本幂等执行（Collection 存在则跳过）。
  - `datasheet_chunks` Collection：11 个字段，dense_vector 1024 维，HNSW 索引 created。
  - `knowledge_notes` Collection：8 个字段，索引 created。
  - `collection.is_ready` 返回 `True`（索引构建完成）。
- **测试方法**：`pytest -q tests/integration/test_milvus_collections.py -m integration`

---

### 1B4：基础设施健康检查脚本
- **目标**：编写统一的健康检查脚本，一次性验证所有基础设施服务状态，供 CI 和运维使用。
- **修改/创建文件**：
  - `scripts/healthcheck.py`（统一健康检查入口）
  - `tests/unit/test_healthcheck_logic.py`（Mock 测试检查逻辑）
- **实现类/函数**：
  - `scripts/healthcheck.py`：
    - `check_postgres(dsn: str) -> ServiceStatus`（执行 `SELECT 1`）
    - `check_milvus(host: str, port: int) -> ServiceStatus`（检查连接 + Collection 存在）
    - `check_redis(url: str) -> ServiceStatus`（执行 `PING`）
    - `check_kuzu(db_path: str) -> ServiceStatus`（验证图数据库文件存在 + 简单查询）
    - `check_all(settings: Settings) -> dict[str, ServiceStatus]`（汇总所有服务状态）
    - `ServiceStatus = dataclass(name, healthy: bool, latency_ms: float, message: str)`
  - 退出码：0 = 全部健康，1 = 有服务不健康
- **验收标准**：
  - 全部服务运行时，`python scripts/healthcheck.py` 输出绿色状态且退出码 0。
  - 某服务关停时，脚本输出该服务不健康且退出码 1（不影响其他服务的检查）。
  - 连接超时控制在 5s 内，不会无限阻塞。
- **测试方法**：`pytest -q tests/unit/test_healthcheck_logic.py`（Mock 外部连接，测试判定逻辑）

---

### 1C1：BGE-M3 Embedding FastAPI 微服务
- **目标**：实现独立的 BGE-M3 Embedding 微服务（端口 8001），加载 `BAAI/bge-m3` 模型，提供 `/encode` 和 `/health` 接口，同时产出 dense + sparse 向量。
- **修改/创建文件**：
  - `src/services/embedding_service.py`（FastAPI app：模型加载 + `/encode` + `/health`）
  - `Dockerfile.embedding`（Docker 构建文件，基于 `python:3.11-slim` + `sentence-transformers`）
  - `docker-compose.services.yml`（模型微服务编排，对齐 §4.5.2）
  - `tests/unit/test_embedding_service_api.py`（Mock 模型，测试 API 契约）
  - `tests/integration/test_embedding_service_live.py`（真实模型加载 + 推理验证）
- **实现类/函数**：
  - `src/services/embedding_service.py`：
    - `app = FastAPI(title="ChipWise Embedding Service")`
    - `load_model(model_name: str) -> FlagModel`（启动时加载 BGE-M3，`@app.on_event("startup")`）
    - `POST /encode`：`encode(request: EncodeRequest) -> EncodeResponse`
      - `EncodeRequest = {texts: list[str], return_sparse: bool = True}`
      - `EncodeResponse = {dense: list[list[float]], sparse: list[dict], dimensions: int, model: str}`
    - `GET /health`：返回 `{status: "ok", model: "BAAI/bge-m3", ready: true}`
- **验收标准**：
  - `POST :8001/encode {"texts": ["hello world"]}` 返回 `dense` 向量维度 = 1024。
  - `return_sparse=True` 时同时返回 sparse 向量（dict 格式：`{token_id: weight}`）。
  - 空输入 `{"texts": []}` 返回 400 错误。
  - `/health` 在模型加载完成前返回 `{ready: false}`，加载后返回 `{ready: true}`。
  - 批量输入（最多 64 条）正确处理，超过限制返回 422。
- **测试方法**：
  - 单元测试（Mock 模型）：`pytest -q tests/unit/test_embedding_service_api.py`
  - 集成测试（真实模型）：`pytest -q tests/integration/test_embedding_service_live.py -m integration`

---

### 1C2：bce-reranker FastAPI 微服务
- **目标**：实现独立的 bce-reranker 微服务（端口 8002），加载 `maidalun1020/bce-reranker-base_v1` 模型，提供 `/rerank` 和 `/health` 接口。
- **修改/创建文件**：
  - `src/services/reranker_service.py`（FastAPI app：模型加载 + `/rerank` + `/health`）
  - `Dockerfile.reranker`（Docker 构建文件）
  - `docker-compose.services.yml`（追加 reranker-service 定义，对齐 §4.5.2）
  - `tests/unit/test_reranker_service_api.py`（Mock 模型，测试 API 契约）
  - `tests/integration/test_reranker_service_live.py`（真实模型加载 + 推理验证）
- **实现类/函数**：
  - `src/services/reranker_service.py`：
    - `app = FastAPI(title="ChipWise Reranker Service")`
    - `load_model(model_name: str) -> CrossEncoder`（启动时加载 bce-reranker）
    - `POST /rerank`：`rerank(request: RerankRequest) -> RerankResponse`
      - `RerankRequest = {query: str, documents: list[str], top_k: int = 10}`
      - `RerankResponse = {results: list[{index: int, score: float, text: str}], model: str}`
    - `GET /health`：返回 `{status: "ok", model: "bce-reranker-base_v1", ready: true}`
- **验收标准**：
  - `POST :8002/rerank {"query": "STM32 clock", "documents": ["doc1", "doc2"]}` 返回按 score 降序排列的结果。
  - `top_k` 参数正确截断结果数量。
  - 空 documents 返回空 results 而非报错。
  - `/health` 在模型加载完成前返回 `{ready: false}`。
- **测试方法**：
  - 单元测试（Mock 模型）：`pytest -q tests/unit/test_reranker_service_api.py`
  - 集成测试（真实模型）：`pytest -q tests/integration/test_reranker_service_live.py -m integration`

---

### 1C3：LM Studio 安装与验证
- **目标**：安装 LM Studio，加载主推理模型和轻量路由模型，验证 OpenAI 兼容 API 支持多模型并发。
- **修改/创建文件**：
  - `scripts/setup_lmstudio.py`（自动检测 + 模型下载 + 配置生成脚本）
  - `scripts/start_services.sh`（一键启动所有服务：LM Studio + Embedding + Reranker + Docker infra）
  - `tests/integration/test_lmstudio_health.py`（验证 LLM API 可用性）
- **实现类/函数**：
  - `scripts/setup_lmstudio.py`：
    - `check_lmstudio() -> bool`（检测 LM Studio 是否已安装并运行）
    - `download_model(model_name: str, quant: str = "Q5_K_M") -> str`（分别下载主推理模型和路由模型）
    - `generate_config(model_path: str, port: int = 1234) -> dict`（生成 LM Studio 启动配置）
  - `scripts/start_services.sh`：
    - 按序启动：Docker infra → LM Studio → Embedding Service → Reranker Service
    - 每个服务启动后等待 healthcheck 通过再启动下一个
- **验收标准**：
  - `curl http://localhost:1234/v1/models` 返回模型列表（包含主推理模型和路由模型，如 `qwen3-35b-q5_k_m` 和 `qwen3-1.7b-q5_k_m`）。
  - 分别向两个模型发送 chat completions 请求并收到有效响应。
  - 主推理模型首 token 延迟 < 15s; 路由模型首 token 延迟 < 2s。
- **测试方法**：`pytest -q tests/integration/test_lmstudio_health.py -m integration`（需要 LM Studio 运行）

---

### 1D1：FastAPI App 骨架 + Health/Readiness 端点
- **目标**：搭建 FastAPI 主应用骨架，包含 CORS 配置、全局异常处理、`/health` 和 `/readiness` 端点。
- **修改/创建文件**：
  - `src/api/main.py`（FastAPI app 工厂函数 + 全局异常处理 + CORS）
  - `src/api/routers/health.py`（`GET /health` + `GET /readiness`）
  - `tests/unit/test_api_health.py`（使用 `httpx.AsyncClient` + `TestClient` 测试）
- **实现类/函数**：
  - `src/api/main.py`：
    - `create_app(settings: Settings) -> FastAPI`（App 工厂，注册路由 + 中间件 + CORS + 异常处理器）
    - `global_exception_handler(request, exc) -> JSONResponse`（统一错误格式：`{error: str, detail: str, trace_id: str}`）
  - `src/api/routers/health.py`：
    - `GET /health`：`health_check() -> {status: "ok", version: str, uptime: float}`（仅检查 App 自身存活）
    - `GET /readiness`：`readiness_check(settings) -> {status: "ready"|"degraded", services: dict}`（检查 PG/Milvus/Redis/Embedding/Reranker 连通性）
- **验收标准**：
  - `uvicorn src.api.main:app` 可正常启动（端口 8080）。
  - `GET :8080/health` 无需认证即可返回 200。
  - `GET :8080/readiness` 返回各下游服务状态（服务不可用时返回 `degraded` 而非 500）。
  - CORS 白名单正确配置（仅允许 `localhost:7860` 等前端域名）。
  - 未知路由返回标准 404 JSON（非 HTML）。
- **测试方法**：`pytest -q tests/unit/test_api_health.py`

---

### 1D2：DI 容器 (dependencies.py)
- **目标**：实现 FastAPI 依赖注入容器，集中管理 Settings、数据库连接池、Redis 客户端、模型服务客户端等共享资源的生命周期。
- **前置条件**：1A3 Settings 已就绪。
- **修改/创建文件**：
  - `src/api/dependencies.py`（DI 容器：`get_settings()`、`get_db_pool()`、`get_redis()`、`get_embedding_client()`、`get_reranker_client()`）
  - `tests/unit/test_dependencies.py`（Mock 外部连接，测试 DI 注入逻辑）
- **实现类/函数**：
  - `src/api/dependencies.py`：
    - `get_settings() -> Settings`（单例，从 YAML 加载配置）
    - `get_db_pool(settings: Settings = Depends(get_settings)) -> asyncpg.Pool`（PostgreSQL 异步连接池）
    - `get_redis(settings: Settings = Depends(get_settings)) -> redis.asyncio.Redis`（Redis 异步客户端）
    - `get_embedding_client(settings: Settings = Depends(get_settings)) -> EmbeddingClient`（BGE-M3 HTTP 客户端）
    - `get_reranker_client(settings: Settings = Depends(get_settings)) -> RerankerClient`（bce-reranker HTTP 客户端）
    - `lifespan(app: FastAPI)`（async context manager：启动时创建连接池，关闭时释放资源）
- **验收标准**：
  - DI 注入在路由中可用（`def endpoint(db=Depends(get_db_pool))`）。
  - 连接池在 App shutdown 时正确关闭（无资源泄漏）。
  - Settings 单例模式：多次 `Depends(get_settings)` 返回同一对象。
  - 外部服务不可用时，DI 创建不崩溃（延迟连接或返回 None + 日志警告）。
- **测试方法**：`pytest -q tests/unit/test_dependencies.py`

---

### 1D3：JWT Auth 中间件 (RS256)
- **目标**：实现 JWT 认证中间件，支持 RS256 签名验证（生产）和 HS256（开发降级），为 §4.12.3 内部 JWT 体系提供验证层。
- **修改/创建文件**：
  - `src/api/middleware/auth.py`（JWT 验证中间件 + RBAC 装饰器 + `get_current_user` Depends）
  - `src/api/routers/auth.py`（`POST /api/v1/auth/register` + `POST /api/v1/auth/login` 本地登录端点）
  - `src/api/schemas/auth.py`（`RegisterRequest`、`LoginRequest`、`TokenResponse`、`UserInfo` Pydantic models）
  - `tests/unit/test_jwt_auth.py`
- **实现类/函数**：
  - `src/api/middleware/auth.py`：
    - `verify_jwt_token(token: str, settings: AuthSettings) -> dict`（验证 JWT 签名 + exp + iss + aud claim）
    - `get_current_user(token: str = Depends(oauth2_scheme), settings = Depends(get_settings)) -> UserInfo`（FastAPI Depends，解析并返回当前用户信息）
    - `require_role(*roles: str)`（RBAC 装饰器，检查 `current_user.role in roles`，不满足返回 403）
  - `src/api/routers/auth.py`：
    - `POST /api/v1/auth/register`：`register(req: RegisterRequest) -> TokenResponse`（bcrypt 哈希密码 + 签发 JWT）
    - `POST /api/v1/auth/login`：`login(req: LoginRequest) -> TokenResponse`（验证密码 + 签发 JWT，含 access_token + refresh_token）
  - JWT Payload 结构对齐 §4.12.3：`{sub, username, role, department, iat, exp, iss: "chipwise-enterprise", aud: "chipwise-api"}`
- **验收标准**：
  - 注册 → 登录 → 拿 Token → 访问受保护端点 E2E 通过。
  - 无 Token / 过期 Token / 篡改 Token 均返回 401 + JSON 错误信息。
  - `require_role("admin")` 装饰的端点：user 角色返回 403，admin 角色返回 200。
  - `/health` 和 `/readiness` 无需 Token（白名单放行）。
  - 密码存储使用 bcrypt，日志中不打印密码或 Token 明文。
- **测试方法**：`pytest -q tests/unit/test_jwt_auth.py`

---

### 1D4：Rate Limiter 中间件 (Redis Token Bucket)
- **目标**：实现基于 Redis 的三级限流中间件，保护 LLM 推理瓶颈，对齐 §4.11.1 设计。
- **前置条件**：1B1 Redis 容器运行中，1D2 DI 可用。
- **修改/创建文件**：
  - `src/api/middleware/rate_limiter.py`（三级限流：Per-User/Minute + Per-User/Hour + Global LLM Semaphore）
  - `tests/unit/test_rate_limiter.py`（Mock Redis，测试限流逻辑）
  - `tests/integration/test_rate_limiter_redis.py`（真实 Redis 集成测试）
- **实现类/函数**：
  - `src/api/middleware/rate_limiter.py`：
    - `RateLimiter.__init__(redis: Redis, settings: AuthSettings)`
    - `RateLimiter.check_rate_limit(user_id: int) -> bool`（Level 1: 30 req/min + Level 2: 500 req/hour，使用 Redis `INCR` + `EXPIRE`）
    - `RateLimiter.acquire_llm_slot(request_id: str, timeout: float = 30.0) -> bool`（Level 3: 全局主模型并发 ≤ 2，Redis `SADD` 信号量）
    - `RateLimiter.release_llm_slot(request_id: str) -> None`（释放信号量 slot）
    - `RateLimitMiddleware(app: ASGIApp)`（ASGI 中间件，被限流时返回 HTTP 429 + `Retry-After` 头）
- **验收标准**：
  - 单用户在 1 分钟内发送 31 次请求，第 31 次返回 HTTP 429 + JSON `{error: "Rate limit exceeded", retry_after: ...}`。
  - 全局主模型信号量：同时 2 个请求持有 slot 时，第 3 个请求排队等待（不是立即拒绝）。路由模型并发上限 10。
  - Redis 断联时降级为进程内计数器（不阻断请求，但限流精度降低）。
  - slot 持有者超时（worker 崩溃场景）后 slot 自动释放（TTL 清理）。
- **测试方法**：
  - 单元测试（Mock Redis）：`pytest -q tests/unit/test_rate_limiter.py`
  - 集成测试（真实 Redis）：`pytest -q tests/integration/test_rate_limiter_redis.py -m integration`

---

### 1D5：Request Logger 中间件
- **目标**：实现请求日志中间件，为每个请求注入 `request_id`（UUID），记录入站/出站日志到结构化 JSON 格式，为后续 TraceContext 奠基。
- **修改/创建文件**：
  - `src/api/middleware/request_logger.py`（ASGI 中间件：注入 request_id + 记录请求/响应日志）
  - `src/observability/logger.py`（增强：`JSONFormatter` 格式化器，输出 JSON Lines）
  - `tests/unit/test_request_logger.py`
- **实现类/函数**：
  - `src/api/middleware/request_logger.py`：
    - `RequestLoggerMiddleware(app: ASGIApp)`
    - 每个请求：生成 `X-Request-ID` UUID → 存入 `request.state.request_id` → 写入响应头
    - 入站日志：`{request_id, method, path, user_agent, user_id(if auth), timestamp}`
    - 出站日志：`{request_id, status_code, latency_ms, response_size}`
    - 敏感信息脱敏：`Authorization` 头仅记录 `Bearer ***`，请求 body 中的 `password` 字段记录为 `***`
  - `src/observability/logger.py`：
    - `JSONFormatter(logging.Formatter)`：输出 JSON Lines 格式日志
    - `get_logger(name: str) -> logging.Logger`：返回带 JSONFormatter 的 logger
- **验收标准**：
  - 每个请求的响应头中包含 `X-Request-ID`。
  - 日志输出为合法 JSON Lines 格式（每行可被 `json.loads()` 解析）。
  - `Authorization` 头和 `password` 字段在日志中已脱敏。
  - 日志包含 `latency_ms` 字段（请求耗时）。
  - `/health` 端点的日志可通过配置屏蔽（避免健康检查刷屏）。
- **测试方法**：`pytest -q tests/unit/test_request_logger.py`

---

### 1E1：Kùzu 图数据库初始化脚本
- **目标**：编写脚本创建 §4.7.4 定义的 6 个节点表 + 7 个关系表，数据目录为 `data/kuzu/`。
- **与 2A6 的关系**：本任务创建初始版 `scripts/init_kuzu.py`（直接使用 `kuzu` 原生 API）；2A6 在 2A5 `KuzuGraphStore` 就绪后重构为通过 GraphStore 抽象层操作，并补充完整的字段属性和集成测试。
- **修改/创建文件**：
  - `scripts/init_kuzu.py`（图 Schema 创建脚本，对齐 §4.7.4）
  - `tests/integration/test_kuzu_schema.py`
- **实现类/函数**：
  - `scripts/init_kuzu.py`：
    - `init_knowledge_graph(db_path: str = "data/kuzu") -> kuzu.Database`
    - `verify_schema(db_path: str) -> bool`（检查 6 节点表 + 7 关系表全部存在）
- **验收标准**：
  - 脚本幂等执行（表存在则跳过, `IF NOT EXISTS`）。
  - 6 节点表：Chip, Parameter, Errata, Document, DesignRule, Peripheral。
  - 7 关系表：HAS_PARAM, ALTERNATIVE, HAS_ERRATA, ERRATA_AFFECTS, DOCUMENTED_IN, HAS_RULE, HAS_PERIPHERAL。
  - 数据文件在 `data/kuzu/` 目录下正确生成。
- **测试方法**：`pytest -q tests/integration/test_kuzu_schema.py -m integration`

---

### 1E2：BaseGraphStore 抽象接口 + KuzuGraphStore 实现
- **目标**：实现图数据库抽象层 (`BaseGraphStore`) 和 Kùzu 具体实现，支持 Cypher 查询、节点 CRUD、子图获取。
- **与 2A5 的关系**：本任务创建骨架代码（抽象接口 + 最小可运行实现 + Factory）；2A5 补齐完整的 CRUD 方法、`get_subgraph()` 多跳查询、错误处理、Tenacity 重试、以及全面的契约测试和集成测试。
- **修改/创建文件**：
  - `src/libs/graph_store/base.py`（`BaseGraphStore` 抽象接口，对齐 §4.7.4）
  - `src/libs/graph_store/kuzu_store.py`（Kùzu 实现）
  - `src/libs/graph_store/factory.py`（`GraphStoreFactory`）
  - `tests/unit/test_graph_store.py`
- **实现类/函数**：
  - `BaseGraphStore`：`execute_cypher()`, `upsert_node()`, `upsert_edge()`, `get_subgraph()`, `health_check()`
  - `KuzuGraphStore(BaseGraphStore)`：Kùzu 嵌入式实现
  - `GraphStoreFactory`：通过 `settings.yaml` 的 `graph_store.backend` 字段切换后端
- **验收标准**：
  - Cypher 查询 `MATCH (c:Chip) RETURN c` 正确执行。
  - `upsert_node` 幂等（重复执行不报错，MERGE 语义）。
  - `health_check()` 返回 True。
  - 通过 Factory 创建实例：`GraphStoreFactory.create({"graph_store": {"backend": "kuzu"}})`。
- **测试方法**：`pytest -q tests/unit/test_graph_store.py`

---

### 1E3：Agent Orchestrator 骨架 + BaseTool + ToolRegistry
- **目标**：搭建 Agent Orchestrator 骨架代码，包含 ReAct 主循环框架、BaseTool 接口、ToolRegistry 自动发现机制。
- **修改/创建文件**：
  - `src/agent/orchestrator.py`（Agent 主循环骨架，对齐 §4.8.1）
  - `src/agent/tools/base_tool.py`（`BaseTool` 抽象基类，对齐 §4.8.2）
  - `src/agent/tool_registry.py`（ToolRegistry 注册 + 自动发现，对齐 §4.8.2）
  - `src/agent/prompt_builder.py`（Agent System Prompt 构建器占位）
  - `src/agent/safety/guardrails.py`（安全护栏占位）
  - `src/agent/safety/token_budget.py`（Token 预算控制占位）
  - `src/agent/safety/output_validator.py`（结构化输出校验器占位，§2.9）
  - `tests/unit/test_agent_orchestrator.py`（Mock LLM + Mock Tool 测试 ReAct 循环）
  - `tests/unit/test_tool_registry.py`（测试 Tool 注册与自动发现）
- **实现类/函数**：
  - `AgentOrchestrator.run()`: ReAct 主循环（可用 Mock LLM 驱动）
  - `BaseTool`: `name`, `description`, `parameters_schema`, `execute()`
  - `ToolRegistry`: `register()`, `get_tool()`, `get_openai_tools_schema()`, `auto_discover()`
  - `TokenBudget`: `consume()`, `remaining`, `exhausted`
- **验收标准**：
  - Mock LLM 返回 Tool Call → Agent 执行 Mock Tool → 获取 Observation → 生成 Final Answer。
  - ToolRegistry 自动发现 `src/agent/tools/` 下的 BaseTool 子类。
  - Token Budget 耗尽时 Agent 自动终止并生成最终答案。
  - `max_iterations` 限制生效，不会无限循环。
- **测试方法**：`pytest -q tests/unit/test_agent_orchestrator.py tests/unit/test_tool_registry.py`

---

#### Phase 1 总产出

Phase 1 完成后应达到以下端到端验证状态：

```bash
# 1. 一键启动基础设施
docker-compose up -d
python scripts/init_db.py
python scripts/init_milvus.py
python scripts/init_kuzu.py        # v3.0: 初始化知识图谱

# 2. 启动模型微服务
python -m src.services.embedding_service  # :8001
python -m src.services.reranker_service   # :8002
# LM Studio 已启动并加载模型  # :1234

# 3. 启动 API Gateway
uvicorn src.api.main:create_app --host 0.0.0.0 --port 8080

# 4. 全部健康检查
python scripts/healthcheck.py
# ✅ PostgreSQL  — healthy (3ms)
# ✅ Milvus      — healthy (5ms)
# ✅ Redis       — healthy (1ms)
# ✅ Kùzu Graph  — healthy (1ms)
# ✅ Embedding   — healthy (2ms)
# ✅ Reranker    — healthy (2ms)
# ✅ LM Studio   — healthy (15ms)

# 5. API 端点可用
curl http://localhost:8080/health           # → 200 {"status": "ok"}
curl http://localhost:8080/readiness        # → 200 {"status": "ready", "services": {...}}
curl -X POST http://localhost:8080/api/v1/auth/register -d '{"username":"test","email":"t@t.com","password":"Passw0rd!"}'
# → 200 {"access_token": "...", "token_type": "bearer"}

# 6. 测试全绿
pytest tests/unit/ -q                       # 全部单元测试通过
pytest tests/integration/ -q -m integration # 全部集成测试通过（需 Docker 运行）
```

### Phase 2: Agentic RAG + Graph RAG Core (Week 3-4)

**目标**: Libs 可插拔层 + Graph RAG 知识图谱 + Agent Orchestrator 端到端可用，对话式 RAG 验证通过。

> **排期原则**
>
> - **先 Libs 层（可插拔接口 + 远程客户端），再 Retrieval 层（Hybrid Search），再 Agent 层（编排 + Tools），最后 Core 服务层（缓存/会话/改写）**。
> - 外部模型服务（BGE-M3 :8001, bce-reranker :8002, LM Studio :1234）在 Phase 1C 已就绪，本阶段仅实现客户端 + 集成验证。
> - Kùzu 为嵌入式进程内数据库，无 Docker 依赖，直接 `pip install kuzu`。

#### Phase 2 子阶段总览

| 子阶段 | 目的 | 任务数 |
|--------|------|--------|
| **2A: Libs 可插拔层（远程客户端 + 图数据库）** | 全部 Base 接口 + Factory + 默认实现 | 6 |
| **2B: Retrieval 检索层** | Hybrid Search + Graph Search + Reranker 编排 | 4 |
| **2C: Agent 框架** | ReAct 编排 + ToolRegistry + Safety + Structured Output Validator (§2.9) + 首批 Tools | 6 |
| **2D: Core 服务层** | ConversationManager + QueryRewriter + GPTCache | 3 |
| **合计** | | **19** |

---

### 2A1：MilvusStore (BaseVectorStore 实现)
- **目标**：实现 `MilvusStore(BaseVectorStore)`，封装 Milvus SDK 的 `upsert` / `query` / `hybrid_search` / `delete` 操作，通过 VectorStoreFactory 注册。
- **修改/创建文件**：
  - `src/libs/vector_store/base.py`（定义 `BaseVectorStore` 抽象接口，含 `upsert`、`query`、`hybrid_search`、`delete`、`get_by_ids`）
  - `src/libs/vector_store/milvus_store.py`（Milvus 实现）
  - `src/libs/vector_store/factory.py`（`VectorStoreFactory`，注册 `milvus` → `MilvusStore`）
  - `tests/unit/test_milvus_store_contract.py`（Mock pymilvus，测试接口契约）
  - `tests/integration/test_milvus_store_roundtrip.py`（真实 Milvus，upsert→query 往返验证）
- **实现类/函数**：
  - `BaseVectorStore`（ABC）：
    - `async upsert(records: list[ChunkRecord], collection: str) -> int`
    - `async query(vector: list[float], top_k: int, filters: dict = None, collection: str = "datasheet_chunks") -> list[RetrievalResult]`
    - `async hybrid_search(dense: list[float], sparse: dict, top_k: int, filters: dict = None) -> list[RetrievalResult]`
    - `async delete(ids: list[str], collection: str) -> int`
    - `async get_by_ids(ids: list[str], collection: str) -> list[dict]`
  - `MilvusStore(BaseVectorStore)`：封装 `pymilvus.Collection`，连接配置从 Settings 读取
  - `VectorStoreFactory.create(settings) -> BaseVectorStore`
- **验收标准**：
  - `provider=milvus` 时 Factory 正确创建 `MilvusStore`。
  - 契约测试：输入/输出 shape 与 `BaseVectorStore` 定义一致。
  - 集成测试：upsert 10 条 1024-dim 向量 → query top_k=5 → 返回非空且 score 降序。
  - 连接失败时抛出含 host:port 信息的可读错误。
- **测试方法**：
  - `pytest -q tests/unit/test_milvus_store_contract.py`
  - `pytest -q tests/integration/test_milvus_store_roundtrip.py -m integration`

---

### 2A2：BGE-M3 Client (BaseEmbedding 实现)
- **目标**：实现 BGE-M3 远程客户端 `BGEM3Client(BaseEmbedding)`，调用 Phase 1C1 部署的 `:8001` 微服务，同时返回 dense + sparse 向量。
- **修改/创建文件**：
  - `src/libs/embedding/base.py`（定义 `BaseEmbedding` 抽象接口）
  - `src/libs/embedding/bgem3_client.py`（HTTP 客户端实现）
  - `src/libs/embedding/factory.py`（`EmbeddingFactory`，注册 `bgem3` → `BGEM3Client`）
  - `tests/unit/test_bgem3_client.py`（Mock HTTP，测试请求/响应契约）
  - `tests/integration/test_bgem3_client_live.py`（真实 :8001 服务验证）
- **实现类/函数**：
  - `BaseEmbedding`（ABC）：
    - `async encode(texts: list[str], return_sparse: bool = True) -> EmbeddingResult`
    - `EmbeddingResult = {dense: list[list[float]], sparse: list[dict], dimensions: int}`
  - `BGEM3Client(BaseEmbedding)`：
    - `__init__(base_url: str, timeout: float = 30.0)`
    - `async encode(texts, return_sparse)` → `POST {base_url}/encode`
    - 内置 Tenacity 重试装饰器（3 次，0.5-10s 指数退避）
  - `EmbeddingFactory.create(settings) -> BaseEmbedding`
- **验收标准**：
  - `encode(["hello world"])` 返回 `dense` 维度 = 1024，`sparse` 为 `{token_id: weight}` dict。
  - 批量输入（≤64 条）正确处理。
  - 服务不可达时 Tenacity 重试 3 次后抛出 `ConnectionError`。
  - Mock 测试覆盖：正常响应、超时、500 错误。
- **测试方法**：
  - `pytest -q tests/unit/test_bgem3_client.py`
  - `pytest -q tests/integration/test_bgem3_client_live.py -m integration`

---

### 2A3：bce-reranker Client (BaseReranker 实现)
- **目标**：实现 bce-reranker 远程客户端 `BCERerankerClient(BaseReranker)`，调用 Phase 1C2 部署的 `:8002` 微服务。
- **修改/创建文件**：
  - `src/libs/reranker/base.py`（定义 `BaseReranker` 抽象接口，含 `NoneReranker` 直通回退）
  - `src/libs/reranker/bce_client.py`（HTTP 客户端实现）
  - `src/libs/reranker/factory.py`（`RerankerFactory`，注册 `bce` + `none`）
  - `tests/unit/test_bce_reranker_client.py`（Mock HTTP）
  - `tests/integration/test_bce_reranker_live.py`（真实 :8002 服务）
- **实现类/函数**：
  - `BaseReranker`（ABC）：
    - `async rerank(query: str, documents: list[str], top_k: int = 10) -> list[RerankResult]`
    - `RerankResult = {index: int, score: float, text: str}`
  - `NoneReranker(BaseReranker)`：直接返回原序（Fallback 用）
  - `BCERerankerClient(BaseReranker)`：
    - `async rerank(query, documents, top_k)` → `POST {base_url}/rerank`
    - Tenacity 重试（3 次，0.5-10s）
  - `RerankerFactory.create(settings) -> BaseReranker`
- **验收标准**：
  - `provider=bce` 时 Factory 创建 `BCERerankerClient`；`provider=none` 时创建 `NoneReranker`。
  - rerank 返回按 score 降序且 `len(results) <= top_k`。
  - 服务不可达时回退到 `NoneReranker`（不阻断主链路）。
- **测试方法**：
  - `pytest -q tests/unit/test_bce_reranker_client.py`
  - `pytest -q tests/integration/test_bce_reranker_live.py -m integration`

---

### 2A4：LMStudio LLM Client (BaseLLM 实现)
- **目标**：实现 LM Studio OpenAI 兼容客户端 `LMStudioClient(BaseLLM)`，调用 `:1234` 本地 LLM 推理（支持 primary + router 双模型角色）。
- **修改/创建文件**：
  - `src/libs/llm/base.py`（定义 `BaseLLM` 抽象接口）
  - `src/libs/llm/lmstudio_client.py`（OpenAI 兼容 HTTP 客户端，支持 chat + tool_calling）
  - `src/libs/llm/factory.py`（`LLMFactory`，注册 `openai_compatible` → `LMStudioClient`）
  - `tests/unit/test_lmstudio_llm.py`（Mock HTTP，测试 chat + tool_calling 格式）
  - `tests/integration/test_lmstudio_llm_live.py`（真实 LM Studio 推理验证）
- **实现类/函数**：
  - `BaseLLM`（ABC）：
    - `async generate(prompt: str, temperature: float = 0.1, max_tokens: int = 4096) -> LLMResponse`
    - `async chat(messages: list[dict], tools: list[dict] = None, **kwargs) -> LLMResponse`
    - `LLMResponse = {text: str, tool_calls: list[ToolCall] | None, usage: {prompt_tokens, completion_tokens}}`
  - `LMStudioClient(BaseLLM)`：
    - 使用 `openai.AsyncOpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")`
    - 支持 `tools` 参数传递 JSON Schema（Agent Tool Calling 核心路径）
    - 支持 `model` 参数切换 primary/router 模型（由 Factory 根据 settings 注入）
    - Tenacity 重试 + CircuitBreaker（§4.11.3 策略：2 次重试，2-15s 退避）
  - `LLMFactory.create(settings, role="primary"|"router") -> BaseLLM`
- **验收标准**：
  - `generate("Hello")` 返回非空 `text`。
  - `chat(messages, tools=[...])` 正确返回 `tool_calls`（Agent 调用的核心能力）。
  - 超时 60s 后抛出 `TimeoutError`（大模型生成较慢）。
  - Mock 测试覆盖：正常 chat、tool_calling 响应、超时、连接失败。
  - Factory 可分别创建 primary 和 router 角色的客户端实例。
- **测试方法**：
  - `pytest -q tests/unit/test_lmstudio_llm.py`
  - `pytest -q tests/integration/test_lmstudio_llm_live.py -m integration`

---

### 2A5：BaseGraphStore + KuzuGraphStore + GraphStoreFactory
- **目标**：在 1E2 骨架基础上，补齐 Kùzu 嵌入式图数据库的完整实现，支持 Cypher 查询、节点/边 CRUD、子图提取、错误处理和重试。
- **与 1E2 的关系**：1E2 已创建 `base.py`/`kuzu_store.py`/`factory.py` 骨架；本任务扩展为生产级实现（完整 CRUD + `get_subgraph()` 多跳 + 契约测试 + 集成测试）。
- **修改/创建文件**：
  - `src/libs/graph_store/__init__.py`
  - `src/libs/graph_store/base.py`（`BaseGraphStore` 抽象接口）
  - `src/libs/graph_store/kuzu_store.py`（Kùzu 嵌入式实现）
  - `src/libs/graph_store/factory.py`（`GraphStoreFactory`，注册 `kuzu`）
  - `tests/unit/test_graph_store_contract.py`（契约测试：输入/输出 shape）
  - `tests/integration/test_kuzu_store_crud.py`（真实 Kùzu CRUD 往返测试）
- **实现类/函数**：
  - `BaseGraphStore`（ABC）：
    - `execute_cypher(query: str, params: dict = None) -> list[dict]`
    - `upsert_node(label: str, properties: dict, key_field: str) -> None`
    - `upsert_edge(from_label: str, from_key: str, to_label: str, to_key: str, rel_type: str, properties: dict = None) -> None`
    - `get_subgraph(node_label: str, node_key: str, max_depth: int = 2) -> dict`
    - `health_check() -> bool`
  - `KuzuGraphStore(BaseGraphStore)`：
    - `__init__(db_path: str = "data/kuzu/")`（创建/加载 Kùzu 嵌入式数据库）
    - 使用 `kuzu.Database` + `kuzu.Connection` 执行 Cypher
  - `GraphStoreFactory.create(settings) -> BaseGraphStore`
- **验收标准**：
  - `provider=kuzu` 时 Factory 创建 `KuzuGraphStore`。
  - `upsert_node("Chip", {"chip_id": 1, "part_number": "STM32F407"}, "chip_id")` 幂等执行。
  - `upsert_edge("Chip", "1", "Chip", "2", "ALTERNATIVE", {"compat_score": 0.85})` 成功。
  - `execute_cypher("MATCH (c:Chip) RETURN c.part_number")` 返回 `[{"c.part_number": "STM32F407"}]`。
  - `get_subgraph("Chip", "1", max_depth=2)` 返回嵌套节点+边结构。
  - `health_check()` 在数据库可用时返回 `True`。
  - 使用临时目录，测试结束后清理。
- **测试方法**：
  - `pytest -q tests/unit/test_graph_store_contract.py`
  - `pytest -q tests/integration/test_kuzu_store_crud.py -m integration`

---

### 2A6：Kùzu Schema 初始化脚本
- **目标**：在 1E1 初始版基础上，重构 `scripts/init_kuzu.py` 以使用 KuzuGraphStore 抽象层，并补齐完整的节点/关系属性字段。
- **与 1E1 的关系**：1E1 创建了可运行的初始版脚本（直接使用 kuzu API）；本任务重构为通过 `GraphStoreFactory` 创建实例，确保与应用代码使用同一抽象层。
- **前置条件**：2A5 KuzuGraphStore 已就绪。
- **修改/创建文件**：
  - `scripts/init_kuzu.py`（Schema 创建脚本）
  - `tests/integration/test_kuzu_schema.py`（验证 Schema 完整性）
- **实现类/函数**：
  - `scripts/init_kuzu.py`：
    - `create_node_tables(conn: kuzu.Connection) -> None`（创建 Chip / Parameter / Errata / Document / DesignRule / Peripheral 六个节点表）
    - `create_relationship_tables(conn: kuzu.Connection) -> None`（创建 HAS_PARAM / ALTERNATIVE / HAS_ERRATA / ERRATA_AFFECTS / DOCUMENTED_IN / HAS_RULE / HAS_PERIPHERAL 七个关系表）
    - `verify_schema(conn: kuzu.Connection) -> bool`（验证全部 13 个表存在）
  - 脚本幂等：表已存在则跳过（`IF NOT EXISTS`）
- **验收标准**：
  - `python scripts/init_kuzu.py` 执行成功，13 个表全部创建。
  - 重复执行不报错（幂等）。
  - Chip 节点含 `chip_id(PK)`, `part_number`, `manufacturer`, `category`, `family`, `status` 字段。
  - ALTERNATIVE 关系含 `compat_type`, `compat_score`, `is_domestic`, `key_differences` 属性。
- **测试方法**：`pytest -q tests/integration/test_kuzu_schema.py -m integration`

---

### 2B1：Milvus 原生 Hybrid Search (Dense+Sparse+RRF)
- **目标**：实现 Milvus 原生混合检索模块，利用 BGE-M3 同时生成的 dense + sparse 向量，通过 `AnnSearchRequest` + `RRFRanker` 完成一次调用融合。
- **前置条件**：2A1 MilvusStore + 2A2 BGEM3Client 已就绪。
- **修改/创建文件**：
  - `src/retrieval/hybrid_search.py`（混合检索核心类）
  - `tests/unit/test_hybrid_search.py`（Mock MilvusStore + BGEM3Client）
  - `tests/integration/test_hybrid_search_e2e.py`（真实 Milvus + BGE-M3）
- **实现类/函数**：
  - `HybridSearch`：
    - `__init__(embedding_client: BaseEmbedding, vector_store: MilvusStore)`
    - `async search(query: str, top_k: int = 20, filters: dict = None, collection: str = "datasheet_chunks") -> list[RetrievalResult]`
      - 步骤 1：`embedding_client.encode(query)` → dense + sparse
      - 步骤 2：构建 `AnnSearchRequest` × 2（dense COSINE + sparse IP）
      - 步骤 3：`collection.hybrid_search(reqs, ranker=RRFRanker(k=60), limit=top_k)`
      - 步骤 4：结果转换为 `RetrievalResult` 列表
    - `_build_filter_expr(filters: dict) -> str`（构建 Milvus 过滤表达式：`part_number == "STM32F407" AND doc_type == "datasheet"`）
- **验收标准**：
  - 输入自然语言查询 → 返回 top_k 结果，每个结果含 `content`、`part_number`、`page`、`score`。
  - filters 正确生效（如 `{"part_number": "STM32F407"}` 仅返回该芯片的 chunks）。
  - dense-only / sparse-only 降级：某路失败时单路检索仍可用。
  - Mock 测试验证 RRFRanker(k=60) 融合逻辑。
- **测试方法**：
  - `pytest -q tests/unit/test_hybrid_search.py`
  - `pytest -q tests/integration/test_hybrid_search_e2e.py -m integration`

---

### 2B2：Graph Search (Kùzu Cypher 查询封装)
- **目标**：封装 Kùzu 图数据库的常用查询模式（替代料查询、勘误查询、子图提取、参数范围搜索），为 `graph_query` Tool 提供底层支持。
- **修改/创建文件**：
  - `src/retrieval/graph_search.py`（图检索封装类）
  - `tests/unit/test_graph_search.py`（Mock KuzuGraphStore）
  - `tests/integration/test_graph_search_e2e.py`（真实 Kùzu + 测试数据）
- **实现类/函数**：
  - `GraphSearch`：
    - `__init__(graph_store: BaseGraphStore)`
    - `async find_alternatives(part_number: str, include_domestic: bool = False) -> list[dict]`（MATCH (c)-[a:ALTERNATIVE]->(alt) ...）
    - `async find_errata_by_peripheral(part_number: str, peripheral: str) -> list[dict]`（三跳查询：Chip→Errata→Peripheral）
    - `async get_chip_subgraph(part_number: str, max_depth: int = 2) -> dict`（返回芯片全景子图：params + alternatives + errata + rules）
    - `async param_range_search(param_name: str, min_val: float, max_val: float) -> list[dict]`（按参数范围搜索芯片）
    - `async execute_custom_cypher(query: str, params: dict = None) -> list[dict]`（透传自定义 Cypher）
- **验收标准**：
  - 四种预定义查询模式均能正确返回结构化结果。
  - `get_chip_subgraph` 返回 2-hop 范围内所有关联节点和边。
  - 芯片不存在时返回空列表（不报错）。
  - 自定义 Cypher 注入防护：禁止 `CREATE`/`DELETE`/`SET` 等写操作（只读查询）。
- **测试方法**：
  - `pytest -q tests/unit/test_graph_search.py`
  - `pytest -q tests/integration/test_graph_search_e2e.py -m integration`

---

### 2B3：Reranker 编排 (bce-reranker 远程调用 + Fallback)
- **目标**：实现 Retrieval 层的 Reranker 编排模块，调用 bce-reranker 远程服务进行精排，失败时自动回退到 `NoneReranker`。
- **修改/创建文件**：
  - `src/retrieval/reranker.py`（Core 层 Reranker 编排）
  - `tests/unit/test_retrieval_reranker.py`（Mock BCERerankerClient）
- **实现类/函数**：
  - `CoreReranker`：
    - `__init__(reranker: BaseReranker, fallback: NoneReranker)`
    - `async rerank(query: str, candidates: list[RetrievalResult], top_k: int = 10) -> list[RetrievalResult]`
      - 正常路径：调用 `self.reranker.rerank()` → 按新 score 重排 candidates
      - 异常路径：catch `Exception` → 日志警告 → 调用 `self.fallback.rerank()` → 返回原序
    - Trace 记录：`rerank` 阶段的 `method`（"bce" | "fallback"）、`reranked` 数量
- **验收标准**：
  - 正常情况下返回按 bce-reranker score 降序排列的 top_k 结果。
  - bce-reranker 不可达时自动回退，不中断主链路，Trace 记录 `method: "fallback"`。
  - top_k 截断正确。
- **测试方法**：`pytest -q tests/unit/test_retrieval_reranker.py`

---

### 2B4：多路结果融合 (fusion.py)
- **目标**：实现多数据源结果融合模块，合并 Milvus 向量检索 + PostgreSQL 结构化查询 + Kùzu 图谱查询的结果，去重并统一排序。
- **修改/创建文件**：
  - `src/retrieval/fusion.py`（多路融合类）
  - `tests/unit/test_fusion.py`
- **实现类/函数**：
  - `MultiSourceFusion`：
    - `fuse(vector_results: list, sql_results: list = None, graph_results: list = None, weights: dict = None) -> list[FusedResult]`
      - 默认权重：`{"vector": 0.6, "sql": 0.2, "graph": 0.2}`
      - 去重策略：按 `chunk_id` 或 `part_number` 去重，保留最高分
      - Graph Boost：如果某 chunk 的 part_number 在图谱结果中出现（如有 errata），score × 1.15
    - `FusedResult = {content, source: str, score: float, metadata: dict}`
- **验收标准**：
  - 三路输入 → 去重 + 加权融合 → 按 score 降序输出。
  - 仅有一路输入时正常工作（其他路为空）。
  - Graph Boost 正确提升包含 errata 关键词的 chunk 权重。
  - 确定性输出：相同输入 → 相同排序。
- **测试方法**：`pytest -q tests/unit/test_fusion.py`

---

### 2C1：BaseTool + ToolRegistry 自动发现
- **目标**：定义 Agent Tool 抽象基类和自动发现注册机制，支持 OpenAI Function Calling JSON Schema 生成。
- **修改/创建文件**：
  - `src/agent/__init__.py`
  - `src/agent/tools/__init__.py`
  - `src/agent/tools/base_tool.py`（`BaseTool` ABC）
  - `src/agent/tool_registry.py`（自动发现 + Schema 生成）
  - `tests/unit/test_tool_registry.py`（用 FakeTool 验证注册和发现逻辑）
- **实现类/函数**：
  - `BaseTool`（ABC）：
    - `name: str` property（如 `"rag_search"`）
    - `description: str` property（工具描述，用于 LLM 系统 prompt）
    - `parameters_schema: dict` property（OpenAI function calling JSON Schema）
    - `async execute(**kwargs) -> Any`（工具执行入口）
  - `ToolRegistry`：
    - `discover(tools_package: str = "src.agent.tools") -> None`（扫描 package 中所有 `BaseTool` 子类并注册）
    - `register(tool: BaseTool) -> None`（手动注册单个 Tool）
    - `get(name: str) -> BaseTool`（按名称获取 Tool）
    - `get_openai_tools_schema() -> list[dict]`（生成全部已注册 Tool 的 OpenAI JSON Schema，供 `tools` 参数传入 LLM）
    - `list_tools() -> list[str]`（返回所有已注册工具名列表）
- **验收标准**：
  - `ToolRegistry.discover()` 能自动发现 `src/agent/tools/` 目录下所有 `BaseTool` 子类。
  - `get_openai_tools_schema()` 输出合法的 OpenAI Function Calling JSON Schema。
  - 重复注册同名 Tool 报错。
  - `get("nonexistent")` 抛出 `KeyError`。
- **测试方法**：`pytest -q tests/unit/test_tool_registry.py`

---

### 2C2：AgentOrchestrator ReAct 主循环
- **目标**：实现 ReAct 模式的 Agent 编排引擎，驱动 Thought→Action→Observation 循环，最多 5 轮迭代，支持并行/串行 Tool 调用。
- **修改/创建文件**：
  - `src/agent/orchestrator.py`（ReAct 主循环）
  - `src/agent/prompt_builder.py`（系统 prompt 构造：注入 Tool Schema + 会话历史 + 安全指令）
  - `tests/unit/test_orchestrator.py`（Mock LLM + FakeTools）
  - `tests/integration/test_orchestrator_e2e.py`（真实 LLM + 真实 Tools）
- **实现类/函数**：
  - `AgentOrchestrator`：
    - `__init__(llm: BaseLLM, tool_registry: ToolRegistry, config: AgentConfig)`
    - `async run(query: str, conversation_history: list[dict] = None, trace: TraceContext = None) -> AgentResult`
      - 构建系统 prompt（含 Tool Schema）
      - 循环最多 `max_iterations`（默认 5）次：
        - 调用 `llm.chat(messages, tools=...)` → 获取 `Thought` + `ToolCalls`
        - 如果 LLM 返回 `tool_calls`：并行/串行执行 Tools → 收集 `Observations`
        - 如果 LLM 返回纯文本（无 tool_calls）：视为 Final Answer → 结束循环
      - 返回 `AgentResult`
    - `AgentConfig = {max_iterations: 5, max_total_tokens: 8192, parallel_tool_calls: True, temperature: 0.1, tool_timeout: 30.0, llm_role: "primary"}`
    - `AgentResult = {answer: str, tool_calls_log: list[AgentStep], total_tokens: int, iterations: int}`
    - `AgentStep = {thought: str, tool_calls: list[ToolCall], observations: list[dict], token_usage: int}`
  - `PromptBuilder`：
    - `build_system_prompt(tools_schema: list[dict]) -> str`
    - `build_messages(system: str, history: list[dict], current_query: str) -> list[dict]`
- **验收标准**：
  - Mock LLM 返回 tool_calls → 对应 FakeTool 被执行 → Observation 正确反馈给 LLM → 最终输出 answer。
  - 迭代次数 ≤ `max_iterations`（超过后强制返回已有信息）。
  - `parallel_tool_calls=True` 时多 Tool 通过 `asyncio.gather` 并行执行。
  - 单 Tool 超时 30s 后该 Tool 返回 `timeout error`，不阻塞其他 Tool。
  - Trace 记录每轮 iteration 的 thought、tool_calls、observations、token_usage。
- **测试方法**：
  - `pytest -q tests/unit/test_orchestrator.py`
  - `pytest -q tests/integration/test_orchestrator_e2e.py -m integration`

---

### 2C3：TokenBudget + SafetyGuardrails + Structured Output Validator
- **目标**：实现 Agent 安全保障：Token 预算控制（防止无限循环消耗 token）、工具输出消毒（防止 prompt injection）和结构化输出校验（§2.9 Pydantic Schema + 领域规则约束）。
- **修改/创建文件**：
  - `src/agent/safety/__init__.py`
  - `src/agent/safety/token_budget.py`（Token 预算计数器）
  - `src/agent/safety/guardrails.py`（输出消毒 + 安全过滤）
  - `src/agent/safety/output_validator.py`（结构化输出校验器，对齐 §2.9）
  - `tests/unit/test_token_budget.py`
  - `tests/unit/test_guardrails.py`
  - `tests/unit/test_output_validator.py`
- **实现类/函数**：
  - `TokenBudget`：
    - `__init__(max_tokens: int = 8192)`
    - `consume(tokens: int) -> None`（累加已消耗 token）
    - `remaining -> int`（剩余预算）
    - `exhausted -> bool`（是否已耗尽）
    - `check_and_raise() -> None`（超预算时抛出 `TokenBudgetExhausted`）
  - `SafetyGuardrails`：
    - `sanitize_tool_output(output: Any) -> Any`（清理 Tool 返回中的潜在 prompt injection 内容：移除 `[SYSTEM]`、`<|im_start|>` 等特殊 token）
    - `validate_tool_call(tool_name: str, arguments: dict) -> bool`（验证 Tool 名称存在 + 参数合法）
    - `check_iteration_limit(current: int, max_iter: int) -> None`（超过最大迭代次数抛出 `MaxIterationExceeded`）
  - `StructuredOutputValidator`（§2.9）：
    - `validate_chip_params(data: dict) -> ValidationResult`（Pydantic Schema 校验 LLM 输出的芯片参数 JSON）
    - `validate_domain_rules(params: list[ChipParam]) -> list[DomainWarning]`（领域规则约束：frequency > 0, voltage 0.1-100V, temperature -273~+500°C）
    - `ValidationResult = {valid: bool, errors: list[str], warnings: list[DomainWarning]}`
    - 校验失败 → 记录 warning, 降级为原始文本（不阻断管线）
- **验收标准**：
  - Token 消耗超过 8192 时 `exhausted` 返回 `True`，`check_and_raise()` 抛出异常。
  - `sanitize_tool_output` 正确清除 `[SYSTEM]`、`<|im_start|>`、`Ignore previous instructions` 等注入字符串。
  - 正常 Tool 输出（纯业务数据）不被误清理。
  - `validate_tool_call("nonexistent_tool", {})` 返回 `False`。
  - `validate_chip_params` 对合法 JSON 返回 `valid=True`；缺少 required 字段返回 `valid=False`。
  - `validate_domain_rules` 对 frequency=-1 返回 DomainWarning；对正常值不报警。
  - Schema 校验失败时不抛出异常，仅降级为原始文本。
- **测试方法**：
  - `pytest -q tests/unit/test_token_budget.py`
  - `pytest -q tests/unit/test_guardrails.py`
  - `pytest -q tests/unit/test_output_validator.py`

---

### 2C4：rag_search Tool (Hybrid + Graph Boost)
- **目标**：实现 RAG 检索 Agent Tool，组合 Hybrid Search + Rerank + 可选 Graph Boost，作为 Agent 最常用的信息获取工具。
- **前置条件**：2B1 HybridSearch + 2B3 CoreReranker + 2B2 GraphSearch 已就绪。
- **修改/创建文件**：
  - `src/agent/tools/rag_search.py`（`RAGSearchTool(BaseTool)`）
  - `tests/unit/test_rag_search_tool.py`（Mock 全部依赖）
  - `tests/integration/test_rag_search_tool_e2e.py`（端到端验证）
- **实现类/函数**：
  - `RAGSearchTool(BaseTool)`：
    - `name = "rag_search"`
    - `parameters_schema`：`{query: str, part_number?: str, doc_type?: enum[datasheet|app_note|errata], top_k?: int(default=10), use_graph_boost?: bool(default=true)}`
    - `async execute(query, part_number, doc_type, top_k, use_graph_boost) -> dict`：
      1. HybridSearch.search(query, top_k=30, filters) → candidates
      2. CoreReranker.rerank(query, candidates, top_k=top_k) → reranked
      3. 如果 `use_graph_boost` 且 `part_number`：GraphSearch.get_chip_subgraph() → 关联 errata 信息 → 提升含 errata 关键词的 chunk score ×1.15
      4. 返回 `{results: [...], total: int}`
- **验收标准**：
  - Agent 调用 `rag_search(query="STM32F407 主频")` → 返回含 `content`、`part_number`、`page`、`score` 的结果列表。
  - `use_graph_boost=True` 时含 errata 信息的 chunk 排名提升。
  - filters 正确传递（`part_number` / `doc_type`）。
  - 无数据时返回空 `results` 而非报错。
- **测试方法**：
  - `pytest -q tests/unit/test_rag_search_tool.py`
  - `pytest -q tests/integration/test_rag_search_tool_e2e.py -m integration`

---

### 2C5：graph_query Tool (4 种图查询)
- **目标**：实现图谱查询 Agent Tool，支持 4 种预定义查询模式 + 自定义 Cypher 透传。
- **修改/创建文件**：
  - `src/agent/tools/graph_query.py`（`GraphQueryTool(BaseTool)`）
  - `tests/unit/test_graph_query_tool.py`（Mock GraphSearch）
  - `tests/integration/test_graph_query_tool_e2e.py`（真实 Kùzu）
- **实现类/函数**：
  - `GraphQueryTool(BaseTool)`：
    - `name = "graph_query"`
    - `parameters_schema`：`{query_type: enum[find_alternatives|find_errata_by_peripheral|chip_subgraph|param_range_search|custom_cypher], part_number?: str, peripheral?: str, param_name?: str, min_val?: float, max_val?: float, cypher?: str}`
    - `async execute(query_type, **kwargs) -> list[dict]`：分发到 `GraphSearch` 对应方法
- **验收标准**：
  - `query_type="find_alternatives"` + `part_number="STM32F407"` → 返回替代芯片列表。
  - `query_type="find_errata_by_peripheral"` + `peripheral="SPI1"` → 返回 SPI 相关勘误。
  - `query_type="chip_subgraph"` → 返回完整子图（params + alternatives + errata + rules）。
  - `query_type="custom_cypher"` 仅允许只读查询（含 `CREATE/DELETE/SET` 时拒绝）。
  - Kùzu 不可用时返回 `{error: "Graph database unavailable"}`（不崩溃）。
- **测试方法**：
  - `pytest -q tests/unit/test_graph_query_tool.py`
  - `pytest -q tests/integration/test_graph_query_tool_e2e.py -m integration`

---

### 2C6：sql_query Tool (参数化 PG 查询)
- **目标**：实现 PostgreSQL 结构化查询 Agent Tool，支持参数化 SQL（防注入），供 Agent 查询芯片参数、文档状态等结构化数据。
- **修改/创建文件**：
  - `src/agent/tools/sql_query.py`（`SQLQueryTool(BaseTool)`）
  - `src/retrieval/sql_search.py`（PG 查询封装）
  - `tests/unit/test_sql_query_tool.py`（Mock DB）
  - `tests/integration/test_sql_query_tool_e2e.py`（真实 PG）
- **实现类/函数**：
  - `SQLSearch`：
    - `__init__(db_pool: asyncpg.Pool)`
    - `async execute(sql: str, params: dict = None) -> {rows: list[dict], column_names: list[str]}`
    - 安全限制：只允许 `SELECT` 语句，禁止 `INSERT/UPDATE/DELETE/DROP`
  - `SQLQueryTool(BaseTool)`：
    - `name = "sql_query"`
    - `parameters_schema`：`{sql: str, params?: dict}`
    - `async execute(sql, params)` → 委托 `SQLSearch.execute()`
- **验收标准**：
  - `sql="SELECT part_number FROM chips WHERE manufacturer = $1"` + `params={"$1": "ST"}` → 返回 ST 芯片列表。
  - 非 SELECT 语句被拒绝并返回明确错误。
  - SQL 注入测试：恶意输入被参数化查询安全处理。
  - 空结果返回 `{rows: [], column_names: [...]}` 而非报错。
- **测试方法**：
  - `pytest -q tests/unit/test_sql_query_tool.py`
  - `pytest -q tests/integration/test_sql_query_tool_e2e.py -m integration`

---

### 2D1：ConversationManager (Redis Session)
- **目标**：实现基于 Redis 的多轮对话管理，每 session 保留最近 10 轮对话，TTL 30 分钟。
- **修改/创建文件**：
  - `src/core/conversation_manager.py`
  - `tests/unit/test_conversation_manager.py`（Mock Redis）
  - `tests/integration/test_conversation_manager_redis.py`（真实 Redis）
- **实现类/函数**：
  - `ConversationManager`：
    - `SESSION_TTL = 1800`（30 分钟）
    - `MAX_TURNS = 10`
    - `__init__(redis: redis.asyncio.Redis)`
    - `async get_history(user_id: int, session_id: str) -> list[dict]`（从 `session:{user_id}:{session_id}` 读取）
    - `async append_turn(user_id: int, session_id: str, role: str, content: str) -> None`（追加 + 截断 + 刷新 TTL）
    - `async clear_session(user_id: int, session_id: str) -> None`
- **验收标准**：
  - 写入 10 轮对话后 `get_history` 返回全部 10 轮。
  - 写入 15 轮后仅返回最近 10 轮（自动截断）。
  - TTL 30 分钟后 session 自动过期（integration 测试可用短 TTL 验证）。
  - Redis 不可用时抛出明确异常（由上层降级处理）。
- **测试方法**：
  - `pytest -q tests/unit/test_conversation_manager.py`
  - `pytest -q tests/integration/test_conversation_manager_redis.py -m integration`

---

### 2D2：QueryRewriter (LLM 代词消解)
- **目标**：使用 LLM 将多轮对话中的代词/省略引用改写为完整独立查询，仅消耗 ~50 tokens。
- **修改/创建文件**：
  - `src/core/query_rewriter.py`
  - `config/prompts/query_rewriter.txt`（改写 prompt 模板）
  - `tests/unit/test_query_rewriter.py`（Mock LLM）
- **实现类/函数**：
  - `QueryRewriter`：
    - `__init__(llm: BaseLLM)`
    - `async rewrite(current_query: str, history: list[dict]) -> str`
      - 无历史 → 直接返回原查询（快路径）
      - 不含代词 → 直接返回（`_needs_rewrite()` 快判）
      - 含代词 → 调用 LLM 改写（`temperature=0, max_tokens=100`）
    - `_needs_rewrite(query: str) -> bool`（检查 "它/这个/那个/其/该/it/this/that" 等代词）
- **验收标准**：
  - `"它的主频是多少"` + 历史含 `"STM32F407"` → 改写为 `"STM32F407 的主频是多少"`。
  - 不含代词的查询直接返回（0 LLM 调用）。
  - 无历史时直接返回原查询。
  - LLM 改写失败时返回原查询（不阻断）。
- **测试方法**：`pytest -q tests/unit/test_query_rewriter.py`

---

### 2D3：GPTCache 语义缓存
- **目标**：实现基于 BGE-M3 + Redis LSH 的语义缓存层，拦截 cosine > 0.95 的相似查询，直接返回缓存响应。
- **修改/创建文件**：
  - `src/cache/semantic_cache.py`（GPTCache 核心）
  - `src/cache/cache_invalidator.py`（PubSub 缓存失效）
  - `tests/unit/test_semantic_cache.py`（Mock Embedding + Redis）
  - `tests/integration/test_semantic_cache_redis.py`（真实 Redis + BGE-M3）
- **实现类/函数**：
  - `SemanticCache`：
    - `SIMILARITY_THRESHOLD = 0.95`
    - `TTL_CONVERSATIONAL = 3600`（1h）
    - `TTL_COMPARISON = 14400`（4h）
    - `__init__(embedding_client: BaseEmbedding, redis: Redis)`
    - `async get(query: str, trace: TraceContext) -> Optional[CachedResponse]`（LSH 桶定位 → 逐条 cosine 比较）
    - `async put(query: str, response: AgentResult, tools_used: list[str]) -> None`（异步写入缓存）
    - `async invalidate_for_chip(part_number: str) -> None`（PubSub 广播清除该芯片缓存）
  - `CacheInvalidator`：
    - `async subscribe(redis: Redis) -> None`（订阅 `cache:invalidate:{part_number}` channel）
    - `async on_message(message) -> None`（收到消息后删除对应缓存）
- **验收标准**：
  - 写入 `"STM32F407 主频"` 的缓存 → 查询 `"STM32F407 的主频是多少"` (cosine > 0.95) → 命中。
  - 查询 `"TI TPS65217 引脚"`（cosine < 0.95）→ 未命中。
  - TTL 过期后 `get` 返回 `None`。
  - `invalidate_for_chip("STM32F407")` 后该芯片相关缓存被清除。
  - Redis 不可用时 `get` 返回 `None`，`put` 静默失败（不阻断主路径）。
- **测试方法**：
  - `pytest -q tests/unit/test_semantic_cache.py`
  - `pytest -q tests/integration/test_semantic_cache_redis.py -m integration`

---

#### Phase 2 总产出

```bash
# Agent 端到端验证：
curl -X POST http://localhost:8080/api/v1/query \
  -H "Authorization: Bearer {token}" \
  -d '{"query": "STM32F407 的主频和 Flash 大小, 有没有 SPI 相关勘误?"}'

# → Agent 自动执行：
#   Iteration 1: [Thought] 需要查芯片参数 + SPI 勘误
#                [Action] rag_search(query="STM32F407 主频 Flash") + graph_query(type="find_errata_by_peripheral", peripheral="SPI")
#                [Observation] {参数数据} + {勘误列表}
#   Iteration 2: [Final Answer] STM32F407 主频 168MHz, Flash 1MB, SPI1 存在以下勘误: ...

# 测试全绿：
pytest tests/unit/ -q -k "phase2 or libs or agent or retrieval or cache"
pytest tests/integration/ -q -m integration
```

### Phase 3: Data Engineering Pipeline (Week 5-7)

**目标**: 完整的异步文档 Ingestion 流水线，支持三路数据采集 + 知识图谱同步。

> **排期原则**
>
> - **先 Celery 基座，再单步 task，再串联 chain，最后接入数据源**。
> - 每个 Celery task 必须可独立测试（Mock 上下游）。
> - 知识图谱同步（graph_sync）作为 Ingestion 链最后一步，从 PG 增量同步到 Kùzu。

#### Phase 3 子阶段总览

| 子阶段 | 目的 | 任务数 |
|--------|------|--------|
| **3A: PDF 解析与结构化提取** | 三级表格提取 + LLM 参数抽取 + Datasheet 感知分片 | 4 |
| **3B: Celery 异步任务链** | Task 定义 + Chain 编排 + 优先级队列 + Graph Sync | 5 |
| **3C: 数据采集三路** | 手动上传 API + Watchdog + Playwright 爬虫 + 跨存储删除 | 4 |
| **合计** | | **13** |

---

### 3A1：PDF 三级表格提取 (pdfplumber→Camelot→PaddleOCR)
- **目标**：实现 §4.6.1 三级递进策略的 PDF 表格提取器，覆盖 ~100% 的 Datasheet 表格类型。
- **修改/创建文件**：
  - `src/ingestion/pdf_extractor.py`（三级表格提取核心类）
  - `tests/unit/test_pdf_extractor.py`（用样例 PDF fixture 验证各级提取）
  - `tests/integration/test_pdf_extractor_real.py`（真实厂商 Datasheet 验证）
  - `tests/fixtures/sample_table.pdf`（含清晰网格线表格）
  - `tests/fixtures/sample_table_stream.pdf`（含无边框空白对齐表格）
  - `tests/fixtures/sample_table_scanned.pdf`（扫描件/图片表格）
- **实现类/函数**：
  - `PDFTableExtractor`：
    - `__init__(settings: Settings)`
    - `extract_tables(pdf_path: str) -> list[ExtractedTable]`（三级递进主入口）
    - `_tier1_pdfplumber(page) -> list[ExtractedTable]`（基于线条坐标检测，覆盖 ~70%）
    - `_tier2_camelot(page) -> list[ExtractedTable]`（lattice + stream 模式，覆盖 ~20%）
    - `_tier3_paddleocr(page) -> list[ExtractedTable]`（PP-Structure OCR，覆盖 ~10%，按需加载模型）
    - `_quality_check(table: ExtractedTable) -> bool`（空单元格率 < 30% 或 accuracy > 0.8）
    - `ExtractedTable = {rows: list[list[str]], page: int, tier: int, quality_score: float, bbox: tuple}`
- **验收标准**：
  - 清晰网格线 PDF → Tier 1 提取成功，quality_score > 0.7。
  - 无边框表格 → Tier 1 失败 → 自动升级 Tier 2 → 提取成功。
  - 扫描件 → Tier 1+2 失败 → 自动升级 Tier 3 → 提取成功。
  - 真实 Datasheet（ST/TI/NXP 各 1 份）表格提取准确率 > 85%。
  - PaddleOCR 按需加载（不在启动时加载，仅 Tier 3 触发时加载）。
- **测试方法**：
  - `pytest -q tests/unit/test_pdf_extractor.py`
  - `pytest -q tests/integration/test_pdf_extractor_real.py -m integration`

---

### 3A2：LLM 结构化参数抽取 (表格→JSON→PG)
- **目标**：使用 LLM 将提取的表格数据转换为标准化芯片参数 JSON，通过 Pydantic Schema 校验 + 领域规则约束（§2.9），写入 PostgreSQL `chip_parameters` 表。
- **修改/创建文件**：
  - `src/ingestion/param_extractor.py`（LLM 参数抽取器）
  - `config/prompts/param_extraction.txt`（参数抽取 prompt 模板，对齐 §4.6.2）
  - `tests/unit/test_param_extractor.py`（Mock LLM，验证 JSON 解析 + Schema 校验逻辑）
  - `tests/integration/test_param_extractor_llm.py`（真实 LLM 验证抽取质量）
- **实现类/函数**：
  - `ParamExtractor`：
    - `__init__(llm: BaseLLM, db_pool: asyncpg.Pool, validator: StructuredOutputValidator)`
    - `async extract_from_table(table: ExtractedTable, chip_part_number: str, page: int) -> list[ChipParam]`
      - 加载 prompt 模板 → 注入表格内容 → 调用 LLM → 解析 JSON 输出 → **Pydantic Schema 校验 → 领域规则检查**
    - `async store_params(params: list[ChipParam], chip_id: int) -> int`（写入 `chip_parameters` 表，ON CONFLICT 更新）
    - `_parse_llm_output(output: str) -> list[ChipParam]`（鲁棒 JSON 解析：支持 markdown code block 包裹、部分 JSON 修复）
    - `ChipParam = {name, category, min_value, typ_value, max_value, unit, condition, source_page, source_table}`
- **验收标准**：
  - Mock LLM 返回标准 JSON → 正确解析为 `ChipParam` 列表。
  - LLM 返回带 markdown code block 的 JSON → 正确提取。
  - LLM 返回非法 JSON → 重试一次，仍失败则记录错误、返回空列表（不阻断）。
  - **Pydantic 校验**: 缺少 required 字段(name/category) → 记录 warning，降级为原始文本（§2.9）。
  - **领域规则**: frequency < 0 或 voltage > 100V → 记录 DomainWarning，参数仍存储但标记 `needs_review=True`。
  - Schema 校验通过率目标 ≥ 98%（§5.2 指标）。
  - 写入 PG 幂等：相同参数重复写入不报错（ON CONFLICT UPDATE）。
  - 真实 LLM 对典型参数表提取准确率 > 90%。
- **测试方法**：
  - `pytest -q tests/unit/test_param_extractor.py`
  - `pytest -q tests/integration/test_param_extractor_llm.py -m integration`

---

### 3A3：Datasheet 感知分片器
- **目标**：实现针对 Datasheet 文档结构的智能分片器，保留章节边界、不截断表格、感知 page break。
- **修改/创建文件**：
  - `src/ingestion/chunking/datasheet_splitter.py`（Datasheet 感知分片器）
  - `tests/unit/test_datasheet_splitter.py`
- **实现类/函数**：
  - `DatasheetSplitter`：
    - `__init__(chunk_size: int = 1024, chunk_overlap: int = 128)`
    - `split(text: str, tables: list[ExtractedTable] = None) -> list[Chunk]`
      - 步骤 1：按章节标题（`#`、`##`、阿拉伯数字标题）切分段落
      - 步骤 2：对超长段落按 `chunk_size` 递归切分（保留句子完整性）
      - 步骤 3：表格区域整体保留不截断（如果表格长于 chunk_size，单独作为一个 chunk）
      - 步骤 4：为每个 chunk 注入元数据：`{page, section_title, chunk_index}`
    - `_detect_section_boundaries(text: str) -> list[int]`（正则检测章节标题位置）
    - `_preserve_table_blocks(text: str, tables: list) -> list[TextBlock]`（标记表格区域为不可分割块）
- **验收标准**：
  - 表格内容完整保留在单个 chunk 中（不跨 chunk 截断）。
  - 章节边界优先作为切分点。
  - 超长纯文本段落按 chunk_size 递归切分，overlap 正确重叠。
  - 每个 chunk 含正确的 `section_title` 元数据。
- **测试方法**：`pytest -q tests/unit/test_datasheet_splitter.py`

---

### 3A4：表格专用分片器 (table_chunker)
- **目标**：对已提取的结构化表格，生成专门的"表格 chunk"用于向量检索，保留表头+上下文。
- **修改/创建文件**：
  - `src/ingestion/chunking/table_chunker.py`（表格专用分片器）
  - `tests/unit/test_table_chunker.py`
- **实现类/函数**：
  - `TableChunker`：
    - `chunk_table(table: ExtractedTable, chip_name: str, section: str) -> list[Chunk]`
      - 小表格（≤ chunk_size）：整表作为一个 chunk，文本格式为 Markdown 表格
      - 大表格：按行分组，每组保留表头 + N 行数据
      - 每个 chunk metadata 含：`{is_table: True, page, section, chip_name}`
    - `_to_markdown_table(rows: list[list[str]]) -> str`（将二维数组转为 Markdown 表格文本）
- **验收标准**：
  - 小表格（10 行）→ 输出 1 个 chunk，内容为完整 Markdown 表格。
  - 大表格（100 行）→ 输出多个 chunk，每个都含表头。
  - `metadata["is_table"]` 为 `True`。
  - Markdown 格式正确（可被渲染器正确显示）。
- **测试方法**：`pytest -q tests/unit/test_table_chunker.py`

---

### 3B1：Celery 基座 + 配置 + Worker 启动
- **目标**：搭建 Celery 异步任务队列基础设施，配置 Redis Broker、任务路由、优先级队列，对齐 §4.6.4。
- **修改/创建文件**：
  - `config/celery_config.py`（Celery 配置：broker_url、result_backend、task_routes、concurrency）
  - `src/ingestion/__init__.py`（Celery app 实例化）
  - `tests/unit/test_celery_config.py`（验证配置正确性）
  - `tests/integration/test_celery_worker.py`（Worker 启动 + 简单 task 执行验证）
- **实现类/函数**：
  - `config/celery_config.py`：
    - `broker_url = "redis://localhost:6379/0"`
    - `result_backend = "redis://localhost:6379/1"`
    - `task_routes`：crawler → `"crawler"` 队列，extract_tables → `"heavy"` 队列，embed_chunks → `"embedding"` 队列
    - `worker_concurrency = 3`，`task_time_limit = 600`，`task_soft_time_limit = 540`
    - `task_acks_late = True`（任务完成后才 ACK，防 Worker 崩溃丢任务）
  - Celery app 实例：`app = Celery("chipwise")`
- **验收标准**：
  - `celery -A src.ingestion.tasks worker -Q default -c 1` 可正常启动。
  - 简单 test task 提交 → 执行 → 结果可从 Redis 获取。
  - 任务路由正确：不同 task 进入对应队列。
  - `task_time_limit` 超时后 task 被 kill。
- **测试方法**：
  - `pytest -q tests/unit/test_celery_config.py`
  - `pytest -q tests/integration/test_celery_worker.py -m integration`

---

### 3B2：Ingestion 单步 Tasks
- **目标**：实现完整 Ingestion 链路的每个 Celery task（§4.6.4），每个 task 可独立测试。
- **修改/创建文件**：
  - `src/ingestion/tasks.py`（全部 Celery task 定义）
  - `tests/unit/test_ingestion_tasks.py`（Mock 外部依赖，逐个测试每个 task）
- **实现类/函数**：
  - `@shared_task download_document(url, manufacturer) -> dict`（下载 PDF → `data/documents/{manufacturer}/`，max_retries=3）
  - `@shared_task validate_and_dedup(doc_info) -> dict`（SHA256 去重：查 PG `documents.file_hash`，已存在则跳过）
  - `@shared_task extract_text(doc_info) -> dict`（pdfplumber 全文本提取 → `doc_info["text"]`）
  - `@shared_task extract_tables(doc_info) -> dict`（三级表格提取 → `doc_info["tables"]`，路由到 `"heavy"` 队列）
  - `@shared_task extract_structured_params(doc_info) -> dict`（LLM 参数抽取 → PG `chip_parameters`，time_limit=120）
  - `@shared_task chunk_text(doc_info) -> dict`（Datasheet 感知分片 → `doc_info["chunks"]`）
  - `@shared_task embed_chunks(doc_info) -> dict`（调用 BGE-M3 :8001 → `doc_info["embeddings"]`，路由到 `"embedding"` 队列）
  - `@shared_task store_vectors(doc_info) -> dict`（Milvus upsert → `doc_info["vector_count"]`）
  - `@shared_task store_metadata(doc_info) -> dict`（PG 写入：documents / chips / chip_parameters / design_rules / errata）
  - `@shared_task notify_completion(doc_info, user_id)`（WebSocket 推送完成通知）
- **验收标准**：
  - 每个 task 的输入/输出 `doc_info` dict 结构明确且稳定。
  - `validate_and_dedup`：已处理文件 → 返回 `doc_info["skipped"] = True` → 后续 task 短路。
  - `extract_tables`：调用 `PDFTableExtractor` 并正确返回表格列表。
  - `extract_structured_params`：time_limit=120s 超时后 task 失败（可重试 2 次）。
  - 每个 task 失败时错误信息写入 `doc_info["error"]`。
- **测试方法**：`pytest -q tests/unit/test_ingestion_tasks.py`

---

### 3B3：Graph Sync Task (PG→Kùzu 增量同步)
- **目标**：实现 Ingestion 链最后一步的知识图谱同步 task，从 PostgreSQL 增量同步到 Kùzu 嵌入式图数据库。
- **修改/创建文件**：
  - `src/ingestion/graph_sync.py`（PG→Kùzu 同步逻辑）
  - `src/ingestion/tasks.py`（追加 `sync_knowledge_graph` task）
  - `tests/unit/test_graph_sync.py`（Mock PG + Kùzu）
  - `tests/integration/test_graph_sync_e2e.py`（真实 PG + Kùzu 往返验证）
- **实现类/函数**：
  - `GraphSynchronizer`：
    - `__init__(db_pool: asyncpg.Pool, graph_store: BaseGraphStore)`
    - `async sync_chip(chip_id: int) -> SyncResult`
      - 步骤 1：从 PG 查询 chip 基本信息 → MERGE Chip 节点
      - 步骤 2：从 PG 查询 chip_parameters → MERGE Parameter 节点 + HAS_PARAM 边
      - 步骤 3：从 PG 查询 chip_alternatives → MERGE ALTERNATIVE 边
      - 步骤 4：从 PG 查询 errata → MERGE Errata 节点 + HAS_ERRATA 边 + ERRATA_AFFECTS 边
      - 步骤 5：从 PG 查询 design_rules → MERGE DesignRule 节点 + HAS_RULE 边
      - 步骤 6：从 PG 查询 documents → MERGE Document 节点 + DOCUMENTED_IN 边
    - `SyncResult = {nodes_created: int, edges_created: int, errors: list[str]}`
  - `@shared_task sync_knowledge_graph(doc_info) -> dict`（Celery task 封装，max_retries=2）
- **验收标准**：
  - PG 中新增芯片 → sync → Kùzu 中可查到对应 Chip 节点及所有关系。
  - 幂等执行：重复 sync 同一芯片不产生重复节点（MERGE 语义）。
  - 单芯片 sync 失败不影响后续芯片（per-chip 粒度）。
  - sync 结果包含统计信息（nodes_created、edges_created）。
- **测试方法**：
  - `pytest -q tests/unit/test_graph_sync.py`
  - `pytest -q tests/integration/test_graph_sync_e2e.py -m integration`

---

### 3B4：Task Chain 编排 + 优先级队列
- **目标**：将全部 Ingestion tasks 编排为 Celery Chain，实现完整的 PDF→可检索 自动流水线，并配置三级优先级队列。
- **修改/创建文件**：
  - `src/ingestion/tasks.py`（追加 `create_ingestion_chain()` 函数）
  - `tests/integration/test_ingestion_chain_e2e.py`（端到端：上传 PDF → 全流程 → Milvus 可检索 + Kùzu 可查询）
- **实现类/函数**：
  - `create_ingestion_chain(url: str, manufacturer: str, user_id: int) -> chain`
    ```python
    chain(
        download_document.s(url, manufacturer),
        validate_and_dedup.s(),
        extract_text.s(),
        extract_tables.s(),
        extract_structured_params.s(),
        chunk_text.s(),
        embed_chunks.s(),
        store_vectors.s(),
        store_metadata.s(),
        sync_knowledge_graph.s(),      # v3.0: 图谱同步
    ) | notify_completion.si(user_id)
    ```
  - 优先级配置：手动上传 (priority=9) > Watchdog (priority=5) > 爬虫 (priority=1)
- **验收标准**：
  - 上传一份 STM32F407 Datasheet → 全自动处理 → Milvus 中有 chunks → PG 中有参数 → Kùzu 中有图谱节点。
  - Chain 中任一 task 失败 → 后续 task 不执行 → `doc_info["status"]` = "failed"。
  - 手动上传 task 优先于爬虫 task 执行（优先级队列验证）。
  - `notify_completion` 在全流程完成后触发。
- **测试方法**：`pytest -q tests/integration/test_ingestion_chain_e2e.py -m integration`

---

### 3B5：任务进度 WebSocket 推送
- **目标**：通过 WebSocket 向前端实时推送 Ingestion 任务进度更新。
- **修改/创建文件**：
  - `src/api/routers/tasks.py`（`GET /api/v1/tasks/{task_id}` 轮询 + `WS /api/v1/tasks/{task_id}/ws` 推送）
  - `tests/unit/test_task_progress.py`（Mock Redis，验证进度格式）
  - `tests/integration/test_task_ws.py`（WebSocket 连接 + 接收进度消息）
- **实现类/函数**：
  - 每个 Celery task 执行时更新 Redis HASH `task:progress:{task_id}`：`{status, progress: 0-100, stage, message, updated_at}`
  - `GET /api/v1/tasks/{task_id}` → 读取 Redis → 返回 JSON 进度
  - `WS /api/v1/tasks/{task_id}/ws` → 每秒推送进度变化直到完成
- **验收标准**：
  - 轮询接口返回正确的 `progress` 百分比和 `stage`（如 `"embedding"`, `"storing_vectors"`）。
  - WebSocket 连接后实时接收进度更新（延迟 < 1s）。
  - 任务完成后 WebSocket 发送 `{status: "completed"}` 后关闭连接。
  - 无效 task_id 返回 404。
- **测试方法**：
  - `pytest -q tests/unit/test_task_progress.py`
  - `pytest -q tests/integration/test_task_ws.py -m integration`

---

### 3C1：手动上传 API (POST /api/v1/documents/upload)
- **目标**：实现文档手动上传 API 端点，接收 PDF 文件并提交 Celery Ingestion 任务。
- **修改/创建文件**：
  - `src/api/routers/documents.py`（`POST /api/v1/documents/upload` + `GET /api/v1/documents` CRUD）
  - `src/api/schemas/documents.py`（`UploadResponse`、`DocumentInfo` Pydantic models）
  - `tests/unit/test_documents_api.py`（Mock Celery，测试 API 契约）
  - `tests/integration/test_upload_e2e.py`（真实文件上传 → Celery 任务创建）
- **实现类/函数**：
  - `POST /api/v1/documents/upload`：
    - 接收 `multipart/form-data`：`file` (PDF) + `manufacturer` (可选) + `collection` (可选)
    - 文件校验：类型白名单 (`.pdf`, `.xlsx`)，大小限制 100MB
    - 保存文件到 `data/documents/{manufacturer}/`
    - 提交 `create_ingestion_chain()` 到 Celery（priority=9: 手动上传最高优先级）
    - 返回 `{task_id, status: "queued", message: "..."}`
  - `GET /api/v1/documents`：列出已处理的文档（PG `documents` 表）
  - `GET /api/v1/documents/{doc_id}`：单个文档详情
- **验收标准**：
  - 上传 PDF → 返回 `task_id` → 轮询 `/tasks/{task_id}` 可看到进度。
  - 非 PDF 文件（如 `.exe`）返回 400 错误。
  - 文件 > 100MB 返回 413 错误。
  - 需要 JWT 认证（无 Token 返回 401）。
- **测试方法**：
  - `pytest -q tests/unit/test_documents_api.py`
  - `pytest -q tests/integration/test_upload_e2e.py -m integration`

---

### 3C2：Watchdog 内网目录监听
- **目标**：使用 `watchdog` 库监听内网共享目录，自动发现新 PDF 并触发 Ingestion。
- **修改/创建文件**：
  - `src/ingestion/watchdog_monitor.py`（文件系统监听器）
  - `tests/unit/test_watchdog_monitor.py`（Mock 文件事件）
- **实现类/函数**：
  - `DatasheetWatchdog`：
    - `__init__(watch_dir: str, celery_app)`
    - `start() -> None`（启动异步文件监听）
    - `stop() -> None`
    - `on_file_created(event: FileCreatedEvent) -> None`
      - 过滤：仅 `.pdf`，忽略 `~$*`、`.tmp`、`.part`
      - 防抖：等待文件最后修改 5s 后再触发（大文件复制场景）
      - 提交 Celery Ingestion 任务（priority=5: 中等优先级）
- **验收标准**：
  - 复制 PDF 到监听目录 → 5s 后自动触发 Ingestion 任务。
  - 临时文件（`.tmp`、`.part`）不触发。
  - 非 PDF 文件不触发。
  - 大文件（100MB）复制过程中不重复触发（防抖机制）。
- **测试方法**：`pytest -q tests/unit/test_watchdog_monitor.py`

---

### 3C3：Playwright 定时爬虫 (ST/TI/NXP)
- **目标**：使用 Playwright 无头浏览器定时抓取 ST/TI/NXP 官网 Datasheet 页面，下载新 PDF。
- **修改/创建文件**：
  - `src/ingestion/crawler.py`（Playwright 爬虫）
  - `tests/unit/test_crawler.py`（Mock Playwright，验证抓取逻辑）
- **实现类/函数**：
  - `DatasheetCrawler`：
    - `MANUFACTURER_CONFIGS`：ST / TI / NXP 各厂商的 base_url、search_pattern、max_per_run
    - `async crawl(manufacturer: str) -> list[str]`（返回下载的 PDF 路径列表）
    - 反爬策略：随机延迟 2-5s、轮换 UA（10 个 Chrome UA）、单次最多 50 个 PDF
    - 每次下载完成 → 提交 Celery Ingestion 任务（priority=1: 最低优先级）
  - Celery Beat 调度：每日凌晨 2:00 执行
- **验收标准**：
  - Mock 环境下能正确解析厂商页面结构 → 提取 PDF 链接 → 模拟下载。
  - 单次运行超过 50 个 PDF 时自动截断。
  - 已下载文件（SHA256 已存在）→ 跳过。
  - 请求间延迟 ≥ 2s。
- **测试方法**：`pytest -q tests/unit/test_crawler.py`

---

### 3C4：DocumentManager 跨存储协调删除
- **目标**：实现文档生命周期管理，删除文档时同时清理 PostgreSQL + Milvus + Kùzu + 文件系统。
- **修改/创建文件**：
  - `src/ingestion/document_manager.py`（跨存储协调删除）
  - `tests/unit/test_document_manager.py`（Mock 各存储，验证协调逻辑）
  - `tests/integration/test_document_manager_e2e.py`（真实跨存储删除验证）
- **实现类/函数**：
  - `DocumentManager`：
    - `__init__(db_pool, vector_store: BaseVectorStore, graph_store: BaseGraphStore)`
    - `async delete_document(doc_id: int) -> DeleteResult`
      - 步骤 1：从 PG `documents` 获取 `file_hash` → 查找关联 chunks
      - 步骤 2：从 Milvus 删除对应 chunk_ids
      - 步骤 3：从 Kùzu 删除关联的 Document 节点及边
      - 步骤 4：从 PG 删除 `documents` + 关联 `chip_parameters`（如该 chip 无其他文档）
      - 步骤 5：删除文件系统中的原始 PDF
      - 步骤 6：触发缓存失效（`cache:invalidate:{part_number}`）
    - `DeleteResult = {pg_deleted: int, milvus_deleted: int, graph_deleted: int, file_deleted: bool}`
- **验收标准**：
  - 删除文档后：PG 无残留记录、Milvus 无残留 chunks、Kùzu 无残留 Document 节点、文件系统无残留 PDF。
  - 部分存储删除失败时：已删除的不回滚，失败的记录在 `DeleteResult.errors` 中。
  - 缓存失效消息正确发布。
- **测试方法**：
  - `pytest -q tests/unit/test_document_manager.py`
  - `pytest -q tests/integration/test_document_manager_e2e.py -m integration`

---

#### Phase 3 总产出

```bash
# 端到端验证：上传 Datasheet → 全流程自动处理 → 可检索可查询
curl -X POST http://localhost:8080/api/v1/documents/upload \
  -H "Authorization: Bearer {token}" \
  -F "file=@STM32F407_Datasheet.pdf" \
  -F "manufacturer=ST"
# → {"task_id": "abc-123", "status": "queued"}

# 监控任务进度
curl http://localhost:8080/api/v1/tasks/abc-123
# → {"status": "processing", "progress": 75, "stage": "embedding"}

# ...完成后...
curl -X POST http://localhost:8080/api/v1/query \
  -d '{"query": "STM32F407 VCC 电压范围"}'
# → Agent 检索到刚入库的 Datasheet chunks → 返回答案 + 引用
```

### Phase 4: Structured Query Tools (Week 8-10)

**目标**: 芯片对比、选型推荐、BOM 审查三个核心 Agent Tool 上线，Agent 可自动组合使用。

> **排期原则**
>
> - **每个 Tool 先写测试再实现**——Mock LLM + Mock PG 验证输入/输出格式，再接真实后端 E2E。
> - 三个 Tool 互相独立，可并行开发。
> - 每个 Tool 应继承 `BaseTool`，由 `ToolRegistry` 自动发现并注册。

#### Phase 4 子阶段总览

| 子阶段 | 目的 | 任务数 |
|--------|------|--------|
| **4A: 芯片对比 Tool** | chip_compare Tool + SQL 对比表构建 + LLM 差异分析 | 2 |
| **4B: 选型推荐 Tool** | chip_select Tool + 结构化过滤 + 国产替代匹配 | 3 |
| **4C: BOM 审查 Tool** | bom_review Tool + Excel 解析 + EOL/冲突检测 + 替代推荐 | 3 |
| **合计** | | **8** |

---

### 4A1：chip_compare Tool (SQL 参数对比 + LLM 分析)
- **目标**：实现芯片横向参数对比 Agent Tool，从 PG 查询参数 → 构建对比表 → LLM 生成差异分析。
- **修改/创建文件**：
  - `src/agent/tools/chip_compare.py`（`ChipCompareTool(BaseTool)`）
  - `config/prompts/chip_comparison.txt`（对比分析 prompt 模板）
  - `tests/unit/test_chip_compare_tool.py`（Mock PG + LLM）
  - `tests/integration/test_chip_compare_e2e.py`（真实 PG + LLM）
- **实现类/函数**：
  - `ChipCompareTool(BaseTool)`：
    - `name = "chip_compare"`
    - `parameters_schema`：`{chip_names: list[str](min=2, max=5), dimensions?: list[str]}`
    - `async execute(chip_names, dimensions) -> dict`：
      1. 对每个芯片执行 SQL 查询 `chip_parameters`（JOIN `chips`）→ 获取参数集
      2. 参数对齐：按 `parameter_name` 对齐，构建 `comparison_table: dict[param_name -> {chip1: val, chip2: val, ...}]`
      3. 如指定 `dimensions`（如 `["electrical", "timing"]`），过滤对应 `parameter_category`
      4. 加载 `chip_comparison.txt` prompt → 注入对比表 → LLM 生成差异分析摘要
      5. 补充 Milvus 检索（每芯片 top_3 设计注意事项）
      6. 返回 `{comparison_table, analysis_text, citations}`
- **验收标准**：
  - `chip_compare(["STM32F407", "STM32F103"])` → 返回完整参数对比表 + 差异分析文本。
  - 对比表含所有共有参数，缺失参数标记为 `null`。
  - 芯片不存在时返回 `{error: "Chip not found: XXX"}`。
  - `dimensions` 过滤正确（仅 `electrical` → 仅返回电气参数）。
  - LLM 分析失败时仍返回对比表（降级）。
- **测试方法**：
  - `pytest -q tests/unit/test_chip_compare_tool.py`
  - `pytest -q tests/integration/test_chip_compare_e2e.py -m integration`

---

### 4A2：芯片对比 API 端点 (POST /api/v1/compare)
- **目标**：提供直接的芯片对比 REST API（不经 Agent 编排），方便前端直接调用。
- **修改/创建文件**：
  - `src/api/routers/compare.py`（`POST /api/v1/compare`）
  - `src/api/schemas/compare.py`（`CompareRequest`、`CompareResponse` Pydantic models）
  - `tests/unit/test_compare_api.py`
- **实现类/函数**：
  - `POST /api/v1/compare`：
    - `CompareRequest = {chip_names: list[str], dimensions?: list[str]}`
    - 内部调用 `ChipCompareTool.execute()`
    - 返回 `CompareResponse = {comparison_table, analysis, citations}`
- **验收标准**：
  - API 返回标准 JSON 对比表。
  - 需 JWT 认证。
  - Pydantic 校验：`chip_names` 长度 < 2 返回 422。
- **测试方法**：`pytest -q tests/unit/test_compare_api.py`

---

### 4B1：chip_select Tool (结构化过滤 + 语义排序)
- **目标**：实现芯片选型推荐 Agent Tool，SQL 结构化过滤缩小范围 → Reranker 语义排序 → LLM 推荐理由。
- **修改/创建文件**：
  - `src/agent/tools/chip_select.py`（`ChipSelectTool(BaseTool)`）
  - `tests/unit/test_chip_select_tool.py`（Mock PG + Reranker + LLM）
  - `tests/integration/test_chip_select_e2e.py`
- **实现类/函数**：
  - `ChipSelectTool(BaseTool)`：
    - `name = "chip_select"`
    - `parameters_schema`：`{criteria: {category?: str, vcc_min?: float, vcc_max?: float, freq_min?: float, package?: str, include_domestic?: bool}}`
    - `async execute(criteria) -> dict`：
      1. 构建 SQL WHERE 子句（参数化防注入） → 查询 `chips` + `chip_parameters` → candidates
      2. 如果有自然语言描述 → Reranker 对 candidates 语义排序（按需求相关性）
      3. `include_domestic=True` → 查询 `chip_alternatives WHERE is_domestic=true`
      4. LLM 生成推荐理由
      5. 返回 `{candidates: list[chip], ranked_summary: str}`
- **验收标准**：
  - `criteria={"category": "MCU", "vcc_min": 1.8, "vcc_max": 3.6}` → 返回符合条件的芯片列表。
  - 结果按 Reranker score 或参数匹配度排序。
  - `include_domestic=True` → 结果包含国产替代信息。
  - 无匹配结果返回空列表 + 友好提示。
- **测试方法**：
  - `pytest -q tests/unit/test_chip_select_tool.py`
  - `pytest -q tests/integration/test_chip_select_e2e.py -m integration`

---

### 4B2：国产替代匹配 (chip_alternatives 集成)
- **目标**：在选型推荐流程中集成国产替代芯片匹配，查询 `chip_alternatives` 表 + Kùzu 图谱 `ALTERNATIVE` 关系。
- **修改/创建文件**：
  - `src/agent/tools/chip_select.py`（扩展 `_find_domestic_alternatives()` 方法）
  - `tests/unit/test_domestic_alternatives.py`
- **实现类/函数**：
  - `ChipSelectTool._find_domestic_alternatives(chip_id: int) -> list[dict]`：
    - 查询 PG `chip_alternatives WHERE original_chip_id = ? AND is_domestic = true`
    - 同时查询 Kùzu `MATCH (c)-[a:ALTERNATIVE {is_domestic: true}]->(alt) WHERE c.chip_id = ?`
    - 合并去重 → 按 `compat_score` 降序
    - 每个结果含：`{part_number, manufacturer, compat_type, compat_score, key_differences}`
- **验收标准**：
  - 有国产替代数据时 → 返回含 `is_domestic: true` 的结果列表。
  - 无国产替代时 → 返回空列表（不报错）。
  - PG 和 Kùzu 结果合并去重（同一芯片不重复）。
- **测试方法**：`pytest -q tests/unit/test_domestic_alternatives.py`

---

### 4B3：chip_alternatives 数据填充脚本
- **目标**：提供替代关系数据的手动录入 + CSV 批量导入工具。
- **修改/创建文件**：
  - `scripts/seed_data.py`（扩展：批量导入 chip_alternatives CSV）
  - `tests/fixtures/chip_alternatives_sample.csv`（样例数据）
  - `tests/unit/test_seed_alternatives.py`
- **实现类/函数**：
  - `scripts/seed_data.py`：
    - `import_alternatives(csv_path: str, db_pool) -> int`（读 CSV → 写入 `chip_alternatives` + 同步 Kùzu `ALTERNATIVE` 边）
    - CSV 格式：`original_part,alternative_part,compat_type,compat_score,is_domestic,key_differences`
  - `POST /api/v1/admin/alternatives`（API 接口，`require_role("admin")`）
- **验收标准**：
  - CSV 导入 10 条记录 → PG + Kùzu 各新增 10 条。
  - 重复导入幂等（ON CONFLICT 更新 score）。
  - 非 admin 角色调用 API 返回 403。
- **测试方法**：`pytest -q tests/unit/test_seed_alternatives.py`

---

### 4C1：bom_review Tool (Excel 解析 + 型号匹配)
- **目标**：实现 BOM 智能审查 Agent Tool，解析 Excel 文件 → 逐行匹配芯片库。
- **修改/创建文件**：
  - `src/agent/tools/bom_review.py`（`BOMReviewTool(BaseTool)`）
  - `tests/unit/test_bom_review_tool.py`（Mock PG + 样例 Excel）
  - `tests/fixtures/sample_bom.xlsx`（样例 BOM 表）
  - `tests/integration/test_bom_review_e2e.py`
- **实现类/函数**：
  - `BOMReviewTool(BaseTool)`：
    - `name = "bom_review"`
    - `parameters_schema`：`{file_path: str}`
    - `async execute(file_path) -> dict`：
      1. `_parse_bom_excel(path)` → `list[BOMItem]`（openpyxl 解析）
      2. 逐行匹配：`SELECT * FROM chips WHERE part_number ILIKE $1`（精确 + 模糊）
      3. 返回 `{bom_review: {total_items, matched, unmatched, eol_warnings, conflicts}, items: list}`
    - `BOMItem = {row_number, part_number, description, quantity, designator, chip_id?, match_status}`
    - `_match_chip(part_number: str) -> MatchResult`（精确匹配 → 前缀匹配 → 返回 None）
- **验收标准**：
  - 样例 BOM（10 行）→ 正确匹配已有芯片 → `match_status` 为 `matched/unmatched/ambiguous`。
  - Excel 格式异常（空行、合并单元格）→ 容错处理不崩溃。
  - 无匹配芯片行标记为 `unmatched`。
  - 返回 summary 统计（total/matched/unmatched）。
- **测试方法**：
  - `pytest -q tests/unit/test_bom_review_tool.py`
  - `pytest -q tests/integration/test_bom_review_e2e.py -m integration`

---

### 4C2：EOL/NRND 检测 + 参数冲突检测
- **目标**：在 BOM 审查流程中追加 EOL/NRND 停产检测和 BOM 描述与实际参数的一致性检查。
- **修改/创建文件**：
  - `src/agent/tools/bom_review.py`（扩展 `_check_eol()` + `_check_conflicts()` 方法）
  - `tests/unit/test_bom_eol_conflict.py`
- **实现类/函数**：
  - `BOMReviewTool._check_eol(chip) -> dict`：
    - 检查 `chips.status`：`EOL` / `NRND` / `obsolete` → 标记 `eol_flag` / `nrnd_flag`
  - `BOMReviewTool._check_conflicts(description: str, chip_id: int) -> list[dict]`：
    - 从 BOM `description` 提取参数声明（如 "3.3V 100MHz LQFP48"）
    - 与 PG `chip_parameters` 实际值比对
    - 不一致项返回 `{param: "VCC", bom_says: "5V", actual: "3.3V"}`
- **验收标准**：
  - 芯片 status="EOL" → `eol_flag=True`。
  - BOM 描述 "5V" 但实际 VCC max=3.6V → 返回冲突。
  - 无冲突时 `parameter_conflicts` 为空列表。
  - Mock 测试覆盖：EOL / NRND / active / 有冲突 / 无冲突。
- **测试方法**：`pytest -q tests/unit/test_bom_eol_conflict.py`

---

### 4C3：替代料自动推荐
- **目标**：对 BOM 中标记为 EOL/NRND 的器件，自动从 `chip_alternatives` + Kùzu 图谱推荐替代料。
- **修改/创建文件**：
  - `src/agent/tools/bom_review.py`（扩展 `_find_alternative()` 方法）
  - `tests/unit/test_bom_alternatives.py`
- **实现类/函数**：
  - `BOMReviewTool._find_alternative(chip_id: int) -> dict | None`：
    - 查询 PG `chip_alternatives WHERE original_chip_id = ? ORDER BY compat_score DESC LIMIT 3`
    - 同时查询 Kùzu 图谱 `MATCH (c)-[a:ALTERNATIVE]->(alt) WHERE c.chip_id = ?`
    - 合并 → 取最高 `compat_score` 的推荐
    - 返回 `{alt_part_number, alt_manufacturer, compat_type, compat_score, key_differences}`
  - 最终 `bom_review` 审查报告中 EOL 行自动附带替代料推荐
- **验收标准**：
  - EOL 芯片有替代 → `alternative` 字段非空，含推荐芯片信息。
  - EOL 芯片无替代 → `alternative` 为 `null`，不报错。
  - `key_differences` 清晰列出替代料与原器件的关键差异。
- **测试方法**：`pytest -q tests/unit/test_bom_alternatives.py`

---

#### Phase 4 总产出

```bash
# 芯片对比验证
curl -X POST http://localhost:8080/api/v1/query \
  -d '{"query": "对比 STM32F407 和 STM32F103 的主频、Flash、功耗"}'
# → Agent 调用 chip_compare Tool → 参数对比表 + 差异分析

# 选型推荐验证
curl -X POST http://localhost:8080/api/v1/query \
  -d '{"query": "推荐一款 1.8-3.3V 100MHz 以上的 ARM Cortex-M4 MCU, 有没有国产替代"}'
# → Agent 调用 chip_select Tool → 推荐列表 + 国产替代 + 推荐理由

# BOM 审查验证
curl -X POST http://localhost:8080/api/v1/query \
  -d '{"query": "请审查我上传的 BOM 表"}'  # (文件已通过 documents/upload 上传)
# → Agent 调用 bom_review Tool → 审查报告 (匹配率/EOL 警告/参数冲突/替代推荐)

pytest tests/unit/ -q -k "chip_compare or chip_select or bom_review"
pytest tests/integration/ -q -m integration -k "phase4"
```

### Phase 5: Advanced Features (Week 11-13)

**目标**: 测试用例生成、设计规则检查、知识沉淀、报告导出四组高级 Agent Tool 上线，全部 10 个 Tools 就绪。

> **排期原则**
>
> - 本阶段聚焦 4 个高级 Tool（`test_case_gen`、`design_rule_check`、`knowledge_search`、`report_export`），每个 Tool 独立可测。
> - 知识沉淀模块（knowledge notes）需同时接入 PG CRUD + Milvus 向量检索。
> - ReportEngine 为纯本地文件生成（Word/PDF/Excel），无外部依赖。

#### Phase 5 子阶段总览

| 子阶段 | 目的 | 任务数 |
|--------|------|--------|
| **5A: 测试用例生成** | test_case_gen Tool + Excel 导出 | 2 |
| **5B: 设计规则检查** | design_rule_check Tool + Errata 填充 + 规则提取 | 3 |
| **5C: 知识沉淀** | knowledge_search Tool + CRUD API + Milvus 向量化 | 2 |
| **5D: 报告导出** | report_export Tool + ReportEngine (Word/PDF/Excel) | 2 |
| **合计** | | **9** |

---

### 5A1：test_case_gen Tool (参数 → LLM 生成测试项)
- **目标**：实现测试用例生成 Agent Tool，基于芯片参数规格 + Datasheet 上下文，由 LLM 自动生成结构化测试项。
- **修改/创建文件**：
  - `src/agent/tools/test_case_gen.py`（`TestCaseGenTool(BaseTool)`）
  - `config/prompts/test_case_gen.txt`（测试用例生成 prompt 模板）
  - `tests/unit/test_case_gen_tool.py`（Mock PG + Milvus + LLM）
  - `tests/integration/test_case_gen_e2e.py`
- **实现类/函数**：
  - `TestCaseGenTool(BaseTool)`：
    - `name = "test_case_gen"`
    - `parameters_schema`：`{chip_name: str}`
    - `async execute(chip_name) -> dict`：
      1. `sql_search.get_chip_parameters(chip_name)` → 获取全部参数
      2. `hybrid_search.search(f"{chip_name} 测试方法 验证 测试条件", top_k=5)` → 检索 App Note 测试上下文
      3. 加载 `test_case_gen.txt` prompt → 注入参数 + 上下文 → LLM 生成（max_tokens=4096）
      4. `_parse_test_cases(llm_output) -> list[TestCase]`（结构化解析）
      5. 返回 `{test_cases: str, structured_cases: list, test_case_count: int}`
    - `TestCase = {test_item, parameter, condition, expected_value, test_method, priority}`
- **验收标准**：
  - 输入芯片型号 → 输出 ≥ 10 个测试项，每项含参数/条件/预期值/测试方法。
  - LLM 输出解析失败时返回原始文本（降级）。
  - 芯片无参数数据时返回友好提示。
- **测试方法**：
  - `pytest -q tests/unit/test_case_gen_tool.py`
  - `pytest -q tests/integration/test_case_gen_e2e.py -m integration`

---

### 5A2：Excel/CSV 导出引擎
- **目标**：将结构化测试用例导出为规范的 Excel/CSV 文件，供硬件工程师直接使用。
- **修改/创建文件**：
  - `src/core/report_engine.py`（通用导出引擎，本任务先实现 Excel/CSV 部分）
  - `tests/unit/test_excel_export.py`
- **实现类/函数**：
  - `ReportEngine`（部分实现）：
    - `export_test_cases_excel(cases: list[TestCase], chip_name: str, output_dir: str = "data/exports/") -> str`
      - 使用 `openpyxl` 生成 Excel：列 = 测试项/参数/条件/预期值/测试方法/优先级
      - 自动设置列宽、表头加粗、冻结首行
      - 返回文件路径
    - `export_test_cases_csv(cases, chip_name, output_dir) -> str`（CSV 备用格式）
- **验收标准**：
  - 导出的 Excel 可被 Microsoft Excel / WPS 正常打开。
  - 列名与 `TestCase` 字段一一对应。
  - 文件名含芯片名和时间戳（如 `STM32F407_test_cases_20260407.xlsx`）。
  - 空数据输入生成仅含表头的空表（不报错）。
- **测试方法**：`pytest -q tests/unit/test_excel_export.py`

---

### 5B1：design_rule_check Tool (规则 + Errata + App Note)
- **目标**：实现设计规则检查 Agent Tool，整合 PG 设计规则 + Kùzu 图谱勘误关联 + Milvus App Note 检索。
- **修改/创建文件**：
  - `src/agent/tools/design_rule.py`（`DesignRuleCheckTool(BaseTool)`）
  - `tests/unit/test_design_rule_tool.py`（Mock PG + Kùzu + Milvus + LLM）
  - `tests/integration/test_design_rule_e2e.py`
- **实现类/函数**：
  - `DesignRuleCheckTool(BaseTool)`：
    - `name = "design_rule_check"`
    - `parameters_schema`：`{chip_name: str}`
    - `async execute(chip_name) -> dict`：
      1. PG 查询 `design_rules WHERE chip_id = ?`（已提取的设计规则）
      2. PG 查询 `errata WHERE chip_id = ? AND status != 'fixed'`（未修复勘误）
      3. Kùzu 多跳查询：`MATCH (c)-[:HAS_ERRATA]->(e)-[:ERRATA_AFFECTS]->(p:Peripheral)` → 勘误影响的外设
      4. Milvus 检索 `"{chip_name} 设计注意事项 layout decoupling"` (doc_type=app_note, top_k=10)
      5. LLM 综合整理：规则 + 勘误 + App Note → 结构化设计检查报告
      6. 返回 `{design_rules: list, errata: list, app_note_citations: list, analysis: str}`
- **验收标准**：
  - 输入芯片型号 → 返回设计规则 + 未修复勘误 + App Note 引用 + 综合分析。
  - 图谱多跳查询正确关联 Errata→Peripheral。
  - 无设计规则/勘误时对应列表为空（不报错）。
  - LLM 分析按 severity 排序（mandatory > recommendation > note）。
- **测试方法**：
  - `pytest -q tests/unit/test_design_rule_tool.py`
  - `pytest -q tests/integration/test_design_rule_e2e.py -m integration`

---

### 5B2：设计规则自动提取 (Ingestion 阶段扩展)
- **目标**：在 Ingestion 流程中自动从 Datasheet 提取设计建议（退耦电容/布局/电源/ESD），写入 `design_rules` 表。
- **修改/创建文件**：
  - `src/ingestion/tasks.py`（扩展 `store_metadata` task，追加设计规则提取逻辑）
  - `config/prompts/design_rule_extraction.txt`（规则提取 prompt 模板）
  - `tests/unit/test_design_rule_extraction.py`（Mock LLM）
- **实现类/函数**：
  - `extract_design_rules(chunks: list[Chunk], chip_id: int, llm: BaseLLM) -> list[DesignRule]`：
    - 筛选含 "decoupling" / "layout" / "注意" / "建议" / "power sequence" 等关键词的 chunks
    - LLM 从匹配 chunks 提取结构化规则：`{rule_type, rule_text, severity, source_page, source_section}`
    - 写入 PG `design_rules` 表
  - `DesignRule.rule_type` 枚举：`decoupling_cap | layout | thermal | power_seq | clock | esd | io_config`
- **验收标准**：
  - 含 "退耦电容" 章节的 Datasheet → 提取到 `rule_type=decoupling_cap` 的规则。
  - 每条规则含 `source_page` + `source_section` 溯源。
  - LLM 提取失败时不阻断 Ingestion 主流程。
- **测试方法**：`pytest -q tests/unit/test_design_rule_extraction.py`

---

### 5B3：Errata 文档解析与数据填充
- **目标**：支持 Errata 文档的专用解析逻辑，提取勘误 ID、影响外设、Workaround，写入 `errata` 表 + Kùzu 图谱。
- **修改/创建文件**：
  - `src/ingestion/tasks.py`（扩展：`doc_type=errata` 时触发专用解析）
  - `tests/unit/test_errata_parser.py`（Mock LLM + 样例 Errata 文本）
  - `tests/fixtures/sample_errata.txt`（样例 Errata 文档片段）
- **实现类/函数**：
  - `parse_errata_document(text: str, chip_id: int, llm: BaseLLM) -> list[ErrataEntry]`：
    - LLM 从 Errata 文本提取结构化条目：
      - `{errata_code, title, severity, status, affected_revisions, affected_peripherals, workaround, fix_revision}`
    - 写入 PG `errata` 表
    - 同步 Kùzu：MERGE Errata 节点 + HAS_ERRATA 边 + ERRATA_AFFECTS→Peripheral 边
  - `ErrataEntry` 对齐 §4.7.1 `errata` 表结构
- **验收标准**：
  - 样例 Errata 文本 → 正确提取勘误 ID、影响外设、Workaround。
  - PG 和 Kùzu 同步写入。
  - `affected_peripherals` 正确拆分为多个 Peripheral 节点关系。
  - 重复导入幂等（ON CONFLICT 更新）。
- **测试方法**：`pytest -q tests/unit/test_errata_parser.py`

---

### 5C1：Knowledge Notes CRUD API + Milvus 向量化
- **目标**：实现知识心得的 CRUD API，用户可对芯片/文档添加标签和心得，写入 PG + Milvus（`knowledge_notes` Collection）。
- **修改/创建文件**：
  - `src/api/routers/knowledge.py`（CRUD：`POST/GET/PUT/DELETE /api/v1/knowledge`）
  - `src/api/schemas/knowledge.py`（Pydantic models）
  - `tests/unit/test_knowledge_api.py`（Mock PG + Milvus）
  - `tests/integration/test_knowledge_crud_e2e.py`
- **实现类/函数**：
  - `POST /api/v1/knowledge`：创建笔记 → PG `knowledge_notes` + BGE-M3 embed → Milvus `knowledge_notes` Collection
  - `GET /api/v1/knowledge?chip_id=&tags=`：按芯片/标签筛选
  - `PUT /api/v1/knowledge/{id}`：更新笔记内容 + 重新 embed
  - `DELETE /api/v1/knowledge/{id}`：PG + Milvus 同步删除
  - Note 类型枚举：`tag | comment | design_tip | errata_link | lesson_learned`
  - RBAC：`user` 角色可编辑自己的；`admin` 可编辑所有
- **验收标准**：
  - 创建笔记 → PG 有记录 + Milvus 有向量。
  - 更新笔记 → Milvus 向量同步更新。
  - 删除笔记 → PG + Milvus 同步清除。
  - `is_public=true` 的笔记所有人可见；`false` 仅创建者可见。
  - GIN 索引支持 tags 数组高效查询。
- **测试方法**：
  - `pytest -q tests/unit/test_knowledge_api.py`
  - `pytest -q tests/integration/test_knowledge_crud_e2e.py -m integration`

---

### 5C2：knowledge_search Tool (团队心得纳入 RAG 检索)
- **目标**：实现知识检索 Agent Tool，从 Milvus `knowledge_notes` Collection 检索团队心得，在 Agent RAG 流程中补充上下文。
- **修改/创建文件**：
  - `src/agent/tools/knowledge_search.py`（`KnowledgeSearchTool(BaseTool)`）
  - `tests/unit/test_knowledge_search_tool.py`（Mock HybridSearch）
- **实现类/函数**：
  - `KnowledgeSearchTool(BaseTool)`：
    - `name = "knowledge_search"`
    - `parameters_schema`：`{query: str, chip_id?: int, top_k?: int(default=5)}`
    - `async execute(query, chip_id, top_k) -> dict`：
      - HybridSearch.search(query, collection="knowledge_notes", top_k, filters={"chip_id": chip_id})
      - 结果含 `{content, note_type, author, tags, page_ref}`
      - 标注来源为 `"team_knowledge"`（与 Datasheet 区分）
- **验收标准**：
  - 团队某人写了 "STM32F407 SPI 需要注意 CS 时序" → `knowledge_search("STM32F407 SPI 注意事项")` → 命中该心得。
  - 结果标注来源 `source: "team_knowledge"` + `author`。
  - 无匹配心得时返回空列表。
- **测试方法**：`pytest -q tests/unit/test_knowledge_search_tool.py`

---

### 5D1：ReportEngine (Word/PDF/Excel 生成)
- **目标**：完善通用报告引擎，支持 Word (docx)、PDF、Excel 三种格式的芯片选型/评估报告生成。
- **修改/创建文件**：
  - `src/core/report_engine.py`（完善：Word + PDF 支持）
  - `config/prompts/report_template.txt`（报告模板）
  - `tests/unit/test_report_engine.py`
- **实现类/函数**：
  - `ReportEngine`：
    - `generate_word(data: dict, title: str, output_dir: str) -> str`（使用 `python-docx` 生成 Word）
    - `generate_pdf(data: dict, title: str, output_dir: str) -> str`（使用 `reportlab` 或 `weasyprint` 生成 PDF）
    - `generate_excel(data: dict, title: str, output_dir: str) -> str`（已在 5A2 实现的 `openpyxl` 逻辑复用）
    - 报告内容：标题 / 芯片概要 / 参数列表 / 对比结论 / 引用来源
- **验收标准**：
  - Word 文件可被 MS Word / WPS 正常打开，格式规范（标题/段落/表格）。
  - PDF 文件可被浏览器/PDF 阅读器正常打开。
  - 输出文件保存到 `data/exports/` 目录。
  - 中文内容正确渲染（无乱码）。
- **测试方法**：`pytest -q tests/unit/test_report_engine.py`

---

### 5D2：report_export Tool (Agent 可调用的报告导出)
- **目标**：实现报告导出 Agent Tool，Agent 可在完成分析后自动生成报告文件。
- **修改/创建文件**：
  - `src/agent/tools/report_export.py`（`ReportExportTool(BaseTool)`）
  - `tests/unit/test_report_export_tool.py`
- **实现类/函数**：
  - `ReportExportTool(BaseTool)`：
    - `name = "report_export"`
    - `parameters_schema`：`{format: enum[word|pdf|excel], data: dict, title?: str}`
    - `async execute(format, data, title) -> dict`：
      - 调用 `ReportEngine.generate_{format}(data, title)`
      - 返回 `{export_path: str, format: str}`
- **验收标准**：
  - `report_export(format="excel", data={...})` → 返回文件路径，文件可正常打开。
  - 不支持的 format 返回 400 错误。
  - 空 data 生成空报告模板（不崩溃）。
- **测试方法**：`pytest -q tests/unit/test_report_export_tool.py`

---

#### Phase 5 总产出

```bash
# 全部 10 个 Agent Tools 已注册
python -c "
from src.agent.tool_registry import ToolRegistry
registry = ToolRegistry()
registry.discover()
print(registry.list_tools())
"
# → ['rag_search', 'graph_query', 'sql_query', 'chip_compare', 'chip_select',
#     'bom_review', 'test_case_gen', 'design_rule_check', 'knowledge_search', 'report_export']

# 复杂查询 Agent 自动组合多 Tool
curl -X POST http://localhost:8080/api/v1/query \
  -d '{"query": "评估 STM32F407, 列出设计注意事项和勘误, 生成测试用例, 并导出 PDF 报告"}'
# → Agent 自动调用: design_rule_check → test_case_gen → report_export → 返回报告路径

pytest tests/unit/ -q -k "phase5 or test_case or design_rule or knowledge or report"
```

### Phase 6: Frontend & Delivery (Week 14-16)

**目标**: 完整的用户界面、SSO 接入、负载测试、端到端验收、文档交付，系统正式上线。

> **排期原则**
>
> - **先 Gradio MVP 快速可用，SSO 集成紧随其后，最后压测 + 安全审计 + 文档收口**。
> - E2E 测试覆盖全部 10 个 Agent Tools 的完整链路。
> - 安全审计按 OWASP Top 10 检查清单逐项验证。

#### Phase 6 子阶段总览

| 子阶段 | 目的 | 任务数 |
|--------|------|--------|
| **6A: Gradio MVP 前端** | 对话界面 + 文档上传 + 流式输出 + 监控仪表盘 + Token 追踪 (§2.11) + Prometheus/Grafana 部署 | 4 |
| **6B: SSO/OIDC 集成** | Keycloak/钉钉/飞书 多 IdP 接入 + JIT Provisioning | 2 |
| **6C: 压测 + 安全审计** | Locust 20 人并发 + OWASP Top 10 + GitHub Code Scanning | 2 |
| **6D: E2E 验收 + 文档** | 全链路测试 + 部署运维文档 + 用户手册 | 3 |
| **合计** | | **11** |

---

### 6A1：Gradio 对话界面 + 文档上传 + 对比展示
- **目标**：搭建 Gradio MVP 前端，提供多 Tab 界面：对话检索、文档上传、芯片对比、BOM 审查。
- **修改/创建文件**：
  - `frontend/gradio_app.py`（Gradio 多 Tab 应用）
  - `tests/unit/test_gradio_app.py`（冒烟测试：页面可加载、Tab 切换正常）
- **实现类/函数**：
  - `frontend/gradio_app.py`：
    - `create_gradio_app(api_base: str) -> gr.Blocks`（Gradio 多 Tab 界面工厂）
    - **Tab 1 - 对话检索**：ChatInterface + 历史记录 → `POST /api/v1/query`
    - **Tab 2 - 文档上传**：File Upload + 进度条 → `POST /api/v1/documents/upload` + `GET /api/v1/tasks/{id}`
    - **Tab 3 - 芯片对比**：2-5 输入框 + 维度选择 → `POST /api/v1/compare` → Markdown 对比表
    - **Tab 4 - BOM 审查**：Excel Upload → `POST /api/v1/bom/review` → 审查报告
    - **Tab 5 - 知识库**：笔记列表 + 创建/编辑 → `CRUD /api/v1/knowledge`
- **验收标准**：
  - `python frontend/gradio_app.py` 启动后 `:7860` 可访问。
  - 5 个 Tab 全部可交互，核心功能链路跑通。
  - 对话 Tab：输入问题 → 返回 Agent 回答 + 引用。
  - 文档上传 Tab：选择 PDF → 上传 → 实时显示进度 → 完成。
  - 对比 Tab：输入 2 个芯片型号 → 显示对比表。
- **测试方法**：`pytest -q tests/unit/test_gradio_app.py`

---

### 6A2：SSE 流式输出 (LLM 生成实时展示)
- **目标**：实现 Server-Sent Events 流式输出，LLM 生成过程实时展示到前端，降低用户感知延迟。
- **修改/创建文件**：
  - `src/api/routers/query.py`（扩展：`POST /api/v1/query/stream` SSE 端点）
  - `frontend/gradio_app.py`（对话 Tab 接入流式输出）
  - `tests/unit/test_sse_stream.py`（Mock LLM 流式响应）
- **实现类/函数**：
  - `POST /api/v1/query/stream`：
    - `async def stream_query(request: QueryRequest) -> StreamingResponse`
    - Agent Orchestrator 的 Final Answer 阶段改为流式生成
    - SSE 消息格式：`data: {"type": "token", "content": "..."}\n\n`（增量 token）
    - 结束消息：`data: {"type": "done", "citations": [...], "trace_id": "..."}\n\n`
  - Gradio ChatInterface 配置 `streaming=True`
- **验收标准**：
  - LLM 生成过程中前端逐字显示（不等全部完成）。
  - SSE 连接在 Agent 完成后正确关闭。
  - 客户端中途断开不会导致服务端资源泄漏。
  - 非流式端点 `POST /api/v1/query` 仍正常工作。
- **测试方法**：`pytest -q tests/unit/test_sse_stream.py`

---

### 6A3：监控仪表盘 (系统状态 + 请求统计 + Token 追踪)
- **目标**：在 Gradio 中添加管理员监控 Tab，展示系统健康状态、请求统计、LLM 利用率和 Token 用量追踪（§2.11）。
- **修改/创建文件**：
  - `frontend/gradio_app.py`（追加 Tab 6: 系统监控，需 admin 角色）
  - `src/api/routers/health.py`（扩展 `/readiness` 返回详细指标）
  - `src/observability/token_tracker.py`（Token 用量追踪 Prometheus metrics，对齐 §2.11）
  - `tests/unit/test_monitoring_tab.py`
  - `tests/unit/test_token_tracker.py`
- **实现类/函数**：
  - **Tab 6 - 系统监控**（admin only）：
    - 服务状态面板：PG / Milvus / Redis / Kùzu / Embedding / Reranker / LLM → 绿/红灯
    - 请求统计：QPS、P50/P95/P99 延迟、缓存命中率（从 `traces.jsonl` 聚合）
    - LLM 监控：当前并发 / 排队深度 / Token 消耗（从 Redis semaphore 读取）
    - **Token 用量追踪**（§2.11）：prompt/completion tokens 分模型（primary/router）、分请求类型（query/ingestion）；日/周/月趋势图
    - Ingestion 状态：任务队列深度、成功率（从 Celery Flower 或 Redis 读取）
    - 文档统计：芯片数 / 文档数 / 参数覆盖率（PG 聚合查询）
  - `TokenTracker`（§2.11）：
    - `record(model: str, request_type: str, prompt_tokens: int, completion_tokens: int)` → 写入 Prometheus Counter
    - `get_daily_summary() -> dict` → 返回当日各模型 Token 消耗汇总
    - Prometheus metrics: `chipwise_llm_tokens_total{model, role, token_type}` (Counter)
- **验收标准**：
  - admin 用户可看到监控 Tab，非 admin 用户看不到。
  - 服务状态实时刷新（10s 自动轮询或手动刷新）。
  - Token 追踪面板正确展示 primary/router 模型的 prompt/completion token 消耗。
  - 各指标数值与实际状态一致。
- **测试方法**：
  - `pytest -q tests/unit/test_monitoring_tab.py`
  - `pytest -q tests/unit/test_token_tracker.py`

---

### 6A4：Prometheus + Grafana Docker 部署
- **目标**：部署 Prometheus 和 Grafana 容器，采集 FastAPI `/metrics` 端点暴露的指标（QPS、延迟、缓存命中率、Token 用量等），并预置 ChipWise 监控仪表盘。为 6A3 `TokenTracker` 的 Prometheus metrics 提供存储和可视化基础设施。
- **前置条件**：6A3 完成（`/metrics` 端点和 `TokenTracker` Prometheus Counter 已就绪）
- **修改/创建文件**：
  - `docker-compose.monitoring.yml`（Prometheus + Grafana 容器定义，挂载配置卷）
  - `config/prometheus/prometheus.yml`（scrape 配置：FastAPI :8080/metrics、BGE-M3 :8001/metrics、bce-reranker :8002/metrics）
  - `config/grafana/provisioning/datasources/prometheus.yml`（自动配置 Prometheus 数据源）
  - `config/grafana/provisioning/dashboards/dashboard.yml`（仪表盘自动加载配置）
  - `config/grafana/dashboards/chipwise-overview.json`（预置仪表盘：系统健康 + 请求统计 + Token 追踪 §2.11 + LLM 并发 + Ingestion 队列深度）
  - `scripts/healthcheck.py`（追加 Prometheus :9090 和 Grafana :3000 健康检查）
  - `tests/integration/test_monitoring_stack.py`
- **实现细节**：
  - **Prometheus**（:9090）：
    - scrape_interval: 15s
    - targets: `fastapi:8080`、`bgem3:8001`、`reranker:8002`
    - 数据保留: 15d（`--storage.tsdb.retention.time=15d`）
    - 内存限制: 512MB（Docker `mem_limit`）
  - **Grafana**（:3000）：
    - 预置仪表盘包含 6 个面板：
      1. 服务健康状态（up/down）
      2. 请求 QPS + P50/P95/P99 延迟
      3. Token 用量追踪（§2.11）：`chipwise_llm_tokens_total` 按 model/role/token_type 分组
      4. LLM 并发与排队深度
      5. 缓存命中率（GPTCache hit/miss ratio）
      6. Ingestion 任务队列深度与成功率
    - admin 默认密码通过环境变量 `GF_SECURITY_ADMIN_PASSWORD` 配置
    - 匿名访问禁用
  - **告警规则**（§5.5 对齐）：
    - 内存利用率 > 85% 持续 5 分钟
    - Schema 校验失败率 > 5%
    - Token 日用量超过预算阈值
    - 服务 down 超过 1 分钟
- **验收标准**：
  - `docker-compose -f docker-compose.monitoring.yml up -d` 启动成功，Prometheus :9090 和 Grafana :3000 可访问。
  - Prometheus Targets 页面显示所有 scrape targets 状态为 `UP`。
  - Grafana 预置仪表盘可正常加载，Token 用量面板有数据展示。
  - 告警规则已加载并处于 inactive 状态（无触发条件时）。
  - `scripts/healthcheck.py` 检查 Prometheus 和 Grafana 健康状态通过。
- **测试方法**：
  - `pytest -q tests/integration/test_monitoring_stack.py`（需要 Docker 运行 Prometheus + Grafana）
  - 手动验证：发送若干请求后检查 Grafana 面板数据更新。

---

### 6B1：SSO Provider 适配器 (Keycloak + 钉钉 + 飞书)
- **目标**：实现 §4.12.1 定义的多 IdP SSO 适配器，支持 Keycloak (OIDC) / 钉钉 (OAuth2) / 飞书 (OAuth2)。
- **修改/创建文件**：
  - `src/auth/__init__.py`
  - `src/auth/sso/__init__.py`
  - `src/auth/sso/base.py`（`BaseSSOProvider` 抽象基类 + `SSOUserInfo` 数据结构）
  - `src/auth/sso/keycloak.py`（`KeycloakProvider(BaseSSOProvider)` OIDC 标准实现）
  - `src/auth/sso/dingtalk.py`（`DingTalkProvider(BaseSSOProvider)` 钉钉 OAuth2 适配）
  - `src/auth/sso/feishu.py`（`FeishuProvider(BaseSSOProvider)` 飞书 OAuth2 适配）
  - `src/auth/sso/factory.py`（`SSOProviderFactory`）
  - `tests/unit/test_sso_providers.py`（Mock HTTP，测试各 Provider 的 OAuth 流程）
- **实现类/函数**：
  - `BaseSSOProvider`（ABC）：
    - `get_authorization_url(state: str, nonce: str) -> str`（生成 IdP 授权 URL）
    - `async exchange_code(code: str, nonce: str) -> SSOUserInfo`（Authorization Code 换取用户信息）
    - `async validate_id_token(id_token: str) -> dict`（JWKS 验证签名）
  - `SSOUserInfo = {sub, email, name, department, groups, avatar_url, raw_claims}`
  - `SSOProviderFactory.create(provider_name: str, config: dict) -> BaseSSOProvider`
  - `KeycloakProvider`：标准 OIDC Discovery + JWKS 验证
  - `DingTalkProvider`：钉钉企业内部应用 OAuth2 流程
  - `FeishuProvider`：飞书自建应用 OAuth2 流程
- **验收标准**：
  - `SSOProviderFactory.create("keycloak", config)` → 返回 `KeycloakProvider` 实例。
  - Mock Keycloak OIDC 流程：`get_authorization_url()` → `exchange_code()` → 返回 `SSOUserInfo`。
  - Mock 钉钉/飞书 OAuth2 流程同样测试通过。
  - JWKS 公钥缓存机制（1h TTL）。
  - 不支持的 provider 类型抛出明确错误。
- **测试方法**：`pytest -q tests/unit/test_sso_providers.py`

---

### 6B2：OIDC 中间件 + JIT Provisioning + 本地降级
- **目标**：实现 §4.12.1 OIDC 认证中间件、§4.12.2 JIT Provisioning（首次登录自动建用户）、§4.12.3 本地登录降级。
- **修改/创建文件**：
  - `src/api/middleware/oidc_auth.py`（OIDC 中间件：JWKS 验证 + IdP 自动发现）
  - `src/auth/sso/jit_provisioning.py`（JIT 用户创建 + IdP 组→RBAC 角色映射）
  - `src/api/routers/auth.py`（扩展：`POST /api/v1/auth/sso/callback` SSO 回调端点）
  - `tests/unit/test_oidc_middleware.py`（Mock JWKS + id_token）
  - `tests/unit/test_jit_provisioning.py`（Mock DB）
  - `tests/integration/test_sso_flow_e2e.py`（如有 Keycloak 测试实例）
- **实现类/函数**：
  - `OIDCAuthMiddleware`：
    - `async get_jwks() -> dict`（从 `/.well-known/openid-configuration` 获取 JWKS，1h 缓存）
    - `async verify_token(token: str) -> dict`（RS256 + JWKS 验证 iss/aud/exp/nonce）
  - `JITProvisioner`：
    - `async provision(sso_user: SSOUserInfo, db) -> User`
      - 首次登录：创建用户 + 角色映射（`chipwise-admin` → `admin`，`chipwise-engineers` → `user`，默认 `viewer`）
      - 已有用户：更新 display_name / department / last_login
  - `POST /api/v1/auth/sso/callback`：
    - 接收 `{code, state}` → SSO Provider exchange_code → JIT Provision → 签发内部 JWT
  - 本地降级：IdP 不可达时 → fallback 到 `POST /api/v1/auth/login`（bcrypt 密码验证）
- **验收标准**：
  - SSO 流程：callback → exchange_code → JIT 建用户 → 返回内部 JWT。
  - 首次登录自动创建用户，角色正确映射。
  - IdP 不可达 → 本地密码登录仍可用，JWT 标记 `sso_provider: "local"`。
  - CSRF state 校验：state 不匹配返回 403。
  - Nonce 重放保护：同一 nonce 二次使用被拒绝。
- **测试方法**：
  - `pytest -q tests/unit/test_oidc_middleware.py`
  - `pytest -q tests/unit/test_jit_provisioning.py`
  - `pytest -q tests/integration/test_sso_flow_e2e.py -m integration`

---

### 6C1：Locust 20 人并发压测
- **目标**：使用 Locust 模拟 20 人并发使用场景，验证系统在峰值负载下的稳定性和延迟指标。
- **修改/创建文件**：
  - `tests/load/locustfile.py`（Locust 测试脚本）
  - `tests/load/test_load_results.py`（自动验证压测结果是否达标）
- **实现类/函数**：
  - `tests/load/locustfile.py`：
    - `class ChipWiseUser(HttpUser)`：
      - `wait_time = between(2, 5)`（模拟真实用户操作间隔）
      - `@task(5) query_rag()`：对话查询（最高频）
      - `@task(3) chip_compare()`：芯片对比
      - `@task(1) upload_document()`：文档上传
      - `@task(1) bom_review()`：BOM 审查
      - 登录获取 JWT → 携带 token 发起请求
  - 压测参数：20 user、ramp-up 30s、持续 5min
- **验收标准**：
  - P95 响应延迟 < 8s（含 LLM 生成）。
  - 无 5xx 错误（HTTP 429 限流不算错误）。
  - LLM 排队深度峰值 ≤ 10。
  - GPTCache 命中率 > 20%（压测过程中有重复查询）。
  - 测试后系统连续 5 分钟无异常日志。
- **测试方法**：`locust -f tests/load/locustfile.py --users 20 --spawn-rate 2 --run-time 5m --host http://localhost:8080`

---

### 6C2：OWASP Top 10 安全审计 + GitHub Code Scanning 配置
- **目标**：按 OWASP Top 10 检查清单逐项审计，确保系统无重大安全漏洞；配置 GitHub Code Scanning (CodeQL) 作为 Phase 1 静态安全分析工具（§5.7）。
- **修改/创建文件**：
  - `tests/security/test_owasp_checklist.py`（自动化安全测试）
  - `.github/workflows/security-scan.yaml`（Trivy + GitHub CodeQL 安全扫描流水线，对齐 §5.7）
  - `docs/SECURITY_AUDIT.md`（安全审计报告）
- **实现类/函数**：
  - **security-scan.yaml**（Phase 1 安全扫描）：
    - GitHub CodeQL: `github/codeql-action/init@v3` + `analyze@v3`（Python 语言）
    - Trivy: `aquasecurity/trivy-action@master`（vuln + secret + misconfig 扫描）
    - SARIF 结果上传至 GitHub Security tab
  - 自动化安全测试项：
    - **A01 访问控制**：无 JWT 访问受保护端点 → 401；低权限用户访问 admin 端点 → 403
    - **A02 加密失败**：密码使用 bcrypt 存储（非明文）；JWT 使用 RS256 签名
    - **A03 注入**：SQL 注入测试（`' OR 1=1 --`）→ 被参数化查询阻止；Cypher 注入 → 只读限制
    - **A04 不安全设计**：上传非 PDF 文件 → 400；文件 > 100MB → 413
    - **A05 安全配置错误**：生产环境 `debug=False`；CORS 白名单检查
    - **A06 脆弱组件**：依赖项无已知 CVE（`pip-audit`）
    - **A07 认证失败**：暴力破解保护（连续 5 次失败后锁定 5 分钟）
    - **A08 数据完整性**：Celery 消息签名验证
    - **A09 日志监控失败**：敏感信息脱敏验证（密码、Token 不出现在日志中）
    - **A10 SSRF**：爬虫 URL 白名单（仅允许 st.com / ti.com / nxp.com）
- **验收标准**：
  - 10 项检查全部通过。
  - 安全审计报告记录每项检查结果和证据。
  - 无 Critical / High 级别漏洞。
- **测试方法**：`pytest -q tests/security/test_owasp_checklist.py`

---

### 6D1：全部 10 个 Agent Tools E2E 测试
- **目标**：编写覆盖全部 10 个 Agent Tools 的端到端集成测试，验证 Agent 自动选择和组合 Tools 的完整能力。
- **修改/创建文件**：
  - `tests/e2e/test_agent_tools_e2e.py`（10 个 Tools 的 E2E 测试用例）
  - `tests/e2e/test_multi_tool_composition.py`（Agent 多 Tool 组合测试）
  - `tests/fixtures/golden_test_set.json`（100+ 条领域 QA 对，覆盖参数查询/对比/选型/勘误等核心场景，用于 §2.10 RAG 质量评估基准）
- **实现类/函数**：
  - 单 Tool E2E（每个至少 1 个用例）：
    - `test_rag_search_e2e()`：对话查询 → 返回含引用的答案
    - `test_graph_query_e2e()`：替代料查询 → 返回图谱结果
    - `test_sql_query_e2e()`：参数查询 → 返回结构化数据
    - `test_chip_compare_e2e()`：2 芯片对比 → 返回对比表
    - `test_chip_select_e2e()`：选型条件 → 返回推荐列表
    - `test_bom_review_e2e()`：上传 BOM → 返回审查报告
    - `test_case_gen_e2e()`：生成测试用例 → 返回 Excel 路径
    - `test_design_rule_e2e()`：设计检查 → 返回规则 + 勘误
    - `test_knowledge_search_e2e()`：搜索团队心得 → 返回结果
    - `test_report_export_e2e()`：导出报告 → 文件可打开
  - 多 Tool 组合 E2E：
    - `test_agent_multi_tool()`：复杂查询 → Agent 自动组合 ≥ 2 个 Tools → 返回综合答案
    - `test_agent_max_iterations()`：需要多轮迭代的查询 → Agent 正确收敛
- **验收标准**：
  - 全部 10 个单 Tool E2E 测试通过。
  - 多 Tool 组合测试：Agent 正确选择 Tools 且最终返回有效答案。
  - 每个测试含 Trace 验证（`trace_id` 存在、stages 完整）。
- **测试方法**：`pytest -q tests/e2e/ -m e2e`

---

### 6D2：部署运维文档
- **目标**：编写完整的安装、配置、运维、故障排查文档，确保运维人员可独立部署和维护系统。
- **修改/创建文件**：
  - `docs/DEPLOYMENT.md`（安装部署指南）
  - `docs/OPERATIONS.md`（运维手册 + 故障排查）
- **文档内容**：
  - **DEPLOYMENT.md**：
    - 硬件要求（AMD Ryzen AI 395 / 128GB / 2TB）
    - 软件依赖安装（Python 3.11 + Docker + LM Studio）
    - 一键部署步骤（`docker-compose up` → `init_db.py` → `init_milvus.py` → `init_kuzu.py` → `start_services.sh`）
    - 配置说明（`settings.yaml` 各字段含义）
    - SSO 配置（Keycloak / 钉钉 / 飞书 的客户端注册步骤）
  - **OPERATIONS.md**：
    - 日常运维命令清单
    - 备份与恢复（PG dump + Milvus snapshot + Kùzu 文件拷贝 + Redis RDB）
    - 故障排查 Playbook（LLM 超时 / Milvus OOM / Celery 积压 / 缓存失效 / 内存峰值告警处理 §3.1）
    - 日志查看与分析（`traces.jsonl` 结构说明）
    - CI/CD 说明：Phase 1 使用 Ruff + mypy + GitHub Code Scanning (CodeQL) + Trivy（§5.7）；Phase X 可选引入 SonarQube
    - Token 用量监控与成本控制（§2.11 Prometheus metrics 说明）
    - 扩容指南（单机 → K8s Helm 部署路径）
- **验收标准**：
  - 按照文档步骤，新机器可从零部署到系统可用。
  - 故障排查 Playbook 覆盖 §4.11.4 降级策略矩阵中的所有场景。
- **测试方法**：人工 Review + 新环境试部署验证。

---

### 6D3：用户使用手册 + README 完善
- **目标**：编写面向终端用户（硬件工程师）的操作指南，完善项目 README。
- **修改/创建文件**：
  - `docs/USER_GUIDE.md`（用户使用手册）
  - `README.md`（完善：项目简介 + 特性 + 快速开始 + 架构图 + 贡献指南）
- **文档内容**：
  - **USER_GUIDE.md**：
    - 登录与账号管理（SSO 登录 / 本地登录）
    - 对话检索使用方法（自然语言提问技巧、引用解读）
    - 芯片对比操作步骤
    - BOM 上传与审查报告解读
    - 选型推荐操作
    - 测试用例导出
    - 知识库使用（添加/搜索团队心得）
    - 常见问题 FAQ
  - **README.md**：
    - 项目愿景与定位
    - 核心技术栈一览
    - 架构图（§4.1 七层架构简化版）
    - 快速开始（5 步上手）
    - 贡献指南 + 行为准则
- **验收标准**：
  - 用户手册覆盖全部 9 大功能模块。
  - README 快速开始步骤验证通过（新用户可按步骤跑通）。
  - 无死链、无过期截图。
- **测试方法**：人工 Review + 新用户试用反馈。

---

#### Phase 6 总产出

```bash
# 系统完整上线验证
docker-compose up -d
python scripts/init_db.py && python scripts/init_milvus.py && python scripts/init_kuzu.py
bash scripts/start_services.sh
python scripts/healthcheck.py
# ✅ All 7 services healthy

uvicorn src.api.main:create_app --host 0.0.0.0 --port 8080
python frontend/gradio_app.py
# → http://localhost:7860 可访问

# 全套测试
pytest tests/unit/ -q                               # 全部单元测试通过
pytest tests/integration/ -q -m integration          # 全部集成测试通过
pytest tests/e2e/ -q -m e2e                         # 全部 E2E 测试通过
pytest tests/security/ -q                            # OWASP 安全检查通过
locust -f tests/load/locustfile.py --headless \
  --users 20 --spawn-rate 2 --run-time 5m \
  --host http://localhost:8080                       # P95 < 8s, 0 errors

# 系统正式交付，20 人团队开始使用
```

---

### 交付里程碑

| 里程碑 | 对应阶段 | 验收节点 | 关键交付物 |
|--------|---------|---------|-----------|
| **M1** | Phase 1 完成 | 全部基础设施 `healthcheck.py` 通过，API `/health` 返回 200 | Docker Compose 全栈 + FastAPI 骨架 + Kùzu 初始化 |
| **M2** | Phase 2 完成 | Agent 对话式 RAG 端到端可用（query → retrieve → answer） | Libs 可插拔层 + Agent ReAct 循环 + 3 个首批 Tools |
| **M3** | Phase 3 完成 | PDF Datasheet 自动入库 + 知识图谱同步完成 | Celery 异步链 + 三路采集 + PG→Kùzu Graph Sync |
| **M4** | Phase 4 完成 | 芯片对比 / 选型 / BOM 审查三个 Tool 可通过 Agent 自动调用 | 3 个业务 Tool + 对应 API 端点 |
| **M5** | Phase 5 完成 | 全部 10 个 Agent Tools 就绪 + 报告可导出 | 4 个高级 Tool + ReportEngine |
| **M6** | Phase 6 完成 | 系统正式上线：Gradio 前端 + SSO + 压测通过 + 文档齐全 | Gradio MVP + SSO + E2E 全绿 + 运维文档 + 用户手册 |
