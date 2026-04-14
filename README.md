# ChipWise Enterprise

> 半导体硬件团队的芯片数据智能检索与分析平台

**ChipWise Enterprise** 基于 **Agentic RAG**（ReAct Agent + Tool Calling）和 **Graph RAG**（Kùzu 知识图谱），为芯片工程师提供自然语言查询、芯片对比、BOM 审查与测试用例生成能力。所有推理在本地单机（AMD Ryzen AI 395，128 GB RAM）运行，通过 LM Studio 驱动，零数据外泄。

---

## 核心特性

| 特性 | 说明 |
|---|---|
| 自然语言查询 | 直接用中文或英文提问，获得带引用来源的精准答案 |
| 芯片对比 | 多维参数并排对比 + 自动推荐国产替代方案 |
| BOM 审查 | 上传 Excel，自动检测 EOL/NRND、设计冲突、替代推荐 |
| 选型推荐 | 描述需求，Agent 自动筛选并排序候选芯片 |
| 测试用例生成 | 基于数据手册和勘误，自动生成结构化测试用例并导出 Excel |
| 知识库 | 团队共享工程笔记，语义搜索快速检索 |
| 本地部署 | 无需云服务，所有数据留在内网 |
| SSO 集成 | 支持 Keycloak、钉钉、飞书企业登录 |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1  Vue3 + Element Plus (production) / Gradio (legacy)│
├─────────────────────────────────────────────────────────────┤
│  Layer 2  FastAPI Gateway :8080  JWT · Rate Limit · CORS     │
├─────────────────────────────────────────────────────────────┤
│  Layer 3  Agent Orchestrator  ReAct (max 5 iter, 8192 tok)  │
├─────────────────────────────────────────────────────────────┤
│  Layer 4  Core Services  QueryRewriter · ConvManager · Cache │
├─────────────────────────────────────────────────────────────┤
│  Layer 5  Model Services                                     │
│           LM Studio :1234  (35B primary + 1.7B router)       │
│           BGE-M3 :8001  (dense+sparse embedding)             │
│           bce-reranker :8002                                 │
├─────────────────────────────────────────────────────────────┤
│  Layer 6  Storage                                            │
│           PostgreSQL :5432 · Milvus :19530 · Redis :6379     │
│           Kùzu (embedded, knowledge graph)                   │
├─────────────────────────────────────────────────────────────┤
│  Layer 7  Libs (Pluggable)                                   │
│           BaseLLM · BaseEmbedding · BaseVectorStore          │
│           BaseReranker · BaseGraphStore                      │
└─────────────────────────────────────────────────────────────┘
```

**10 个 Agent Tools**：`rag_search` · `graph_query` · `sql_query` · `chip_compare` · `chip_select` · `bom_review` · `test_case_gen` · `design_rule_check` · `knowledge_search` · `report_export`

---

## 技术栈

| 层次 | 技术选型 |
|---|---|
| 推理模型 | LM Studio（Qwen3-35B 主模型 + Qwen3-1.7B 路由） |
| Embedding | BGE-M3（dense 1024维 + sparse，单次调用） |
| 向量库 | Milvus Standalone（Hybrid Search + RRF Reranker） |
| 知识图谱 | Kùzu（嵌入式，openCypher，零端口） |
| 关系数据库 | PostgreSQL 16 + asyncpg |
| 缓存/队列 | Redis 7（GPTCache 语义缓存 + Celery Broker） |
| 任务队列 | Celery 5（3 Worker Pool + Beat 调度器） |
| API 框架 | FastAPI + Pydantic v2 + uvicorn |
| 前端 | Vue3 + Element Plus（production） / Gradio 4（legacy, deprecated） |
| 监控 | Prometheus + Grafana（Token 追踪 §2.11） |
| 安全 | JWT RS256 + bcrypt + OIDC + CodeQL + Trivy |

---

## 快速开始

### 前提条件

- Python 3.11+
- Docker & Docker Compose v2
- LM Studio（已加载 35B 主模型 + 1.7B 路由模型）

### 5 步上手

```bash
# 1. 克隆仓库
git clone <repo-url> chipwise-enterprise && cd chipwise-enterprise

# 2. 配置环境
cp config/settings.yaml.example config/settings.yaml
# 编辑 settings.yaml，填写 llm.primary.model 和 llm.router.model
export PG_PASSWORD="your-pg-password"
export REDIS_PASSWORD="your-redis-password"
export JWT_SECRET_KEY="$(openssl rand -hex 32)"

# 3. 启动基础设施
docker compose up -d

# 4. 初始化数据库
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python scripts/init_milvus.py
python scripts/init_kuzu.py

# 5. 启动服务
bash scripts/start_services.sh
python scripts/healthcheck.py   # 验证全部 7 个服务健康
```

访问前端：`http://localhost:5173`（Vue3 dev server）或 `http://localhost:7860`（Gradio legacy）
API 文档：`http://localhost:8080/docs`

### 前端开发（Vue3，推荐）

```bash
cd frontend/web
npm install
npm run dev          # Dev server at http://localhost:5173
npm run build        # Production build
npm run test:run     # Vitest unit tests (19 tests)
npx playwright test  # E2E tests (14 specs)
```

### Gradio Legacy MVP（已废弃）

```bash
pip install gradio
python -c "from frontend.gradio_app import create_gradio_app; create_gradio_app().launch()"
# Warning: DeprecationWarning will be emitted
```

详细部署步骤见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。

---

## 文档索引

| 文档 | 说明 |
|---|---|
| [docs/ENTERPRISE_DEV_SPEC.md](docs/ENTERPRISE_DEV_SPEC.md) | 完整架构规格（v5.5，单一事实来源） |
| [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) | 11 阶段 113 任务开发计划 |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | 安装部署指南（含 SSO 配置） |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | 运维手册（备份、故障排查、CI/CD） |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | 用户使用手册（面向硬件工程师） |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构总览 + Mermaid 图（10 分钟入门） |
| [docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md) | OWASP Top 10 安全审计报告 |
| [docs/SECURITY_BASELINE.md](docs/SECURITY_BASELINE.md) | 安全扫描基线（Bandit/pip-audit/npm-audit） |
| [docs/COMPLIANCE.md](docs/COMPLIANCE.md) | 许可证合规 + SBOM |
| [docs/COVERAGE_GAPS.md](docs/COVERAGE_GAPS.md) | 测试覆盖率 gap 分析 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献指南（分支策略、PR 流程） |
| [CLAUDE.md](CLAUDE.md) | AI 助手上下文（架构摘要、编码规范） |

---

## 项目进度

所有 11 个阶段、113 个任务已全部完成（100%）。

| Phase | 任务数 | 核心交付 |
|---|---|---|
| Phase 1 | 18 | 项目骨架、Docker 基础设施、FastAPI 网关、Kùzu + Agent 骨架 |
| Phase 2 | 19 | Libs 可插拔层、Hybrid+Graph 检索、Agent ReAct 循环、3 个基础 Tool |
| Phase 3 | 13 | PDF 提取、Celery 任务链、3 种数据摄取源（上传/监控/爬虫） |
| Phase 4 | 8 | chip_compare、chip_select、bom_review 业务 Tool |
| Phase 5 | 9 | test_case_gen、design_rule_check、knowledge_search、report_export |
| Phase 6 | 11 | Gradio UI、SSO/OIDC、压测、E2E 测试、监控、运维文档 |
| Phase 7 | 3 | Chunking 策略 + eval harness |
| Phase 8 | 6 | 生产化：SSO→Redis、JIT→PG、LM Studio health |
| Phase 9 | 8 | Lint/mypy 零化、integration_nollm 分层、本地 docker friendly |
| Phase 10 | 6 | Vue3 可用化：组件、守卫、refresh、Vitest 19 tests |
| Phase 11 | 12 | 工程化加固：CI、pre-commit、监控、安全、Docker、文档、E2E |

---

## 贡献指南

1. 从 `develop` 分支创建 feature 分支：`git checkout -b feature/my-feature develop`
2. 实现功能并编写测试（单元测试覆盖率 ≥ 75%）
3. 确保通过 `ruff check src tests` 和 `mypy src`
4. 向 `develop` 提交 PR，需 ≥1 位 Reviewer 审批 + CI 全绿
5. 发布经理在阶段边界将 `develop` 合并至 `main`

详见 [CONTRIBUTING.md](CONTRIBUTING.md) 和 [CLAUDE.md](CLAUDE.md) 中的开发工作流章节。

---

## 许可证

内部使用。未经授权不得分发。
