# 1. 项目概述

## 1.1 系统定位

**ChipWise Enterprise** 是一套面向半导体硬件研发团队的 **芯片数据智能检索与分析平台**。系统以 Datasheet / Application Note / Errata 等技术文档为知识底座，通过 **Agentic RAG**（Agent 驱动的检索增强生成）+ **Graph RAG**（知识图谱增强检索）技术，为 20 人规模的工程团队提供自然语言驱动的芯片参数查询、横向对比、选型推荐、BOM 审查、测试用例生成及知识沉淀等一站式智能服务。系统核心为 ReAct Agent Orchestrator，通过 Tool Calling 动态编排检索和分析任务；同时构建「芯片-参数-替代料-勘误」四元知识图谱，实现多跳关系推理。

全部算力基于 **AMD Ryzen AI 395 单机平台**（128GB / 2TB）本地化部署，确保技术文档和设计数据**零外泄**。

## 1.2 关键技术能力

| 维度 | 技术方案 |
|------|----------|
| **存储引擎** | PostgreSQL 15+ / Milvus Standalone / Redis 7 |
| **LLM 推理** | LM Studio 本地多模型调度: 主推理模型 (如 35B 多模态) + 轻量路由模型 (如 1-3B)，均通过 OpenAI 兼容 API |
| **Embedding** | BGE-M3 常驻 FastAPI 微服务 |
| **Rerank** | bce-reranker-base_v1 常驻 FastAPI 微服务 |
| **任务调度** | Celery + Redis 异步分布式任务队列 |
| **并发能力** | 20 人 SSO/OIDC 鉴权 + GPTCache 语义缓存 + 限流 |
| **检索策略** | Agentic RAG: ReAct Agent + Hybrid/Graph 多路召回 |
| **知识图谱** | Kùzu 嵌入式图数据库 — 芯片/参数/替代料/勘误四元知识图谱 |
| **智能编排** | ReAct/Tool Calling Agent Orchestrator (LLM 驱动动态工具调用) |
| **文档解析** | 三级表格提取 (pdfplumber / Camelot / PaddleOCR) |
| **接口层** | FastAPI REST/WebSocket + Gradio/Vue3 前端 |
| **用户系统** | SSO/OIDC (Keycloak/钉钉/飞书) + RBAC 权限模型 |
| **部署方式** | Docker Compose + Systemd (Phase 1) → Helm + K8s (Phase X 扩展) |
| **容错机制** | CircuitBreaker + Tenacity 指数退避重试 |
| **向量数据库** | Milvus Standalone (Phase 1) → Milvus Cluster (Phase X, 百万级扩展) |
| **CI/CD** | GitHub Actions 四阶段流水线 (Ruff + Trivy + GitHub Code Scanning + 滚动更新) |

## 1.3 核心设计原则

1. **接口隔离与工厂模式** — `BaseLLM`、`BaseEmbedding`、`BaseVectorStore`、`BaseReranker` 等抽象基类 + `Factory` 注册机制，保证组件零代码热切换。
2. **核心数据契约** — `Document`、`Chunk`、`ChunkRecord`、`ProcessedQuery`、`RetrievalResult` 五大类型贯穿全链路，新增子类型扩展而非破坏性修改。
3. **TraceContext 全链路追踪** — 每次请求生成唯一 `trace_id`，各阶段通过 `record_stage()` 显式埋点。
4. **配置驱动行为** — 所有组件选型、参数调优通过 `settings.yaml` 声明式管理。
5. **优雅降级** — 每个可选组件（Reranker / LLM Enrichment / Vision LLM）均有 `None` 或 `disabled` 模式，局部故障不阻塞主链路。
6. **Agent Tools 单一职责** — 每个 Agent Tool 独立可测、可监控、可恢复，LLM 驱动动态编排。

---
