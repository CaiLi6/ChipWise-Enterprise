# 2. 核心特点

本章面向技术决策者，以图表为主、文字为辅，概述系统八大核心能力。详细实现请参见第 4 章对应小节。

## 2.1 Agentic RAG 智能编排

系统采用 **ReAct Agent Orchestrator** 替代传统的固定意图路由 + 管线模式。Agent 通过 LLM 推理自主决策调用哪些工具、以何种顺序组合，支持复杂查询的动态多步编排。

| 维度 | v2.0 IntentRouter | v3.0 Agent Orchestrator |
|------|-------------------|------------------------|
| **路由决策** | 规则引擎 + LLM 分类 (静态 1:1 映射) | LLM ReAct 推理 (动态 N:M 工具组合) |
| **复杂查询** | 只能路由到 1 条管线 | 可自动组合多个 Tool |
| **新功能扩展** | 需修改 IntentRouter 规则 + 新建 Pipeline | 仅需注册新 Tool |
| **图谱利用** | 不支持 | 原生支持 graph_query Tool |
| **错误恢复** | 无 (管线失败即失败) | Agent 可根据错误信息决定换策略 |
| **可解释性** | 仅 intent 分类结果 | 完整的 Thought→Action→Observation 链 |

> 详见 [§4.8 Agent 编排架构](#48-agent-编排架构)

## 2.2 Graph RAG 知识图谱

基于 **Kùzu 嵌入式图数据库** 构建「芯片-参数-替代料-勘误」四元知识图谱，支持多跳关系推理。

| 维度 | Neo4j Community | Kùzu |
|------|----------------|------|
| **部署方式** | 独立 JVM 进程 / Docker | **嵌入式** (Python pip install, 进程内) |
| **运维负担** | 需管理 JVM 堆、日志、备份 | **零运维** (文件目录即数据库) |
| **内存占用** | 最低 1-2 GB JVM | **~200 MB** 基础 + mmap 按需 |
| **Cypher 兼容** | 原生 Cypher (完整) | **openCypher 子集** (覆盖 90%+ 常用查询) |
| **本项目适配** | 过重 (20 人团队 / 单机部署) | **最佳** (嵌入式零开销, 芯片数据规模 < 50 万节点) |

```
┌──────────────────── 芯片领域知识图谱 ────────────────────┐
│                                                          │
│   ┌─────────┐   HAS_PARAM    ┌────────────┐             │
│   │  Chip   │───────────────▶│ Parameter  │             │
│   │─────────│                │────────────│             │
│   │ part_no │   ALTERNATIVE  │ name       │             │
│   │ mfr     │◀──────────────▶│ value/unit │             │
│   │ category│                └────────────┘             │
│   │ status  │                                           │
│   └────┬────┘                                           │
│        │                                                │
│        │ HAS_ERRATA          ┌────────────┐             │
│        ├────────────────────▶│  Errata    │             │
│        │                     │────────────│             │
│        │                     │ errata_id  │             │
│        │                     │ severity   │             │
│        │ DOCUMENTED_IN       │ workaround │             │
│        ├────────────────────▶└────────────┘             │
│        │                     ┌────────────┐             │
│        │                     │ Document   │             │
│        │                     │────────────│             │
│        │                     │ doc_type   │             │
│        │ HAS_RULE            │ file_hash  │             │
│        ├────────────────────▶└────────────┘             │
│        │                     ┌────────────┐             │
│        │                     │ DesignRule │             │
│        │                     │────────────│             │
│        │                     │ rule_type  │             │
│        │                     │ severity   │             │
│        │  ERRATA_AFFECTS     └────────────┘             │
│        │  (Errata)──────────▶(Peripheral)               │
│        │                     ┌────────────┐             │
│        │                     │ Peripheral │             │
│        │  HAS_PERIPHERAL     │────────────│             │
│        └────────────────────▶│ name (SPI, │             │
│                              │ USART...) │             │
│                              └────────────┘             │
└──────────────────────────────────────────────────────────┘
```

> 详见 [§4.7.4 Kùzu 图谱 Schema](#474-kùzu-图谱-schema)

## 2.3 多路混合检索

BGE-M3 同时产出 dense 和 sparse 向量，Milvus 2.4+ 原生支持混合检索 + RRF 融合，完全替代旧版自建 BM25 索引 + 手动 RRF 代码。代码量减少约 60%，且检索精度更高（BGE-M3 的稀疏向量比传统 BM25 更强）。

v3.0 在向量检索基础上新增图谱信号增强排序，形成 **Hybrid Search + Graph Boost** 三路召回架构。

> 详见 [§4.7.2 Milvus 向量空间](#472-milvus-向量空间)

## 2.4 三级 PDF 表格提取

Datasheet 中的表格是芯片参数的核心载体。由于 PDF 格式的异构性，采用三级递进策略：

```
PDF 页面输入
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  Tier 1: pdfplumber (默认, 覆盖 ~70% 表格)                  │
│  • 基于线条坐标检测表格边界, 质量检查: 空单元格率 < 30%      │
│  • 耗时: ~0.1s/page                                         │
└──────────┬───────────────────────────────────────────────────┘
           │ (质量检查未通过)
           ▼
┌──────────────────────────────────────────────────────────────┐
│  Tier 2: Camelot (补充, 覆盖 ~20% 表格)                     │
│  • lattice + stream 模式, 合并单元格智能处理                 │
│  • 质量检查: accuracy_score > 0.8, 耗时: ~0.5s/page         │
└──────────┬───────────────────────────────────────────────────┘
           │ (quality score 仍不达标)
           ▼
┌──────────────────────────────────────────────────────────────┐
│  Tier 3: PaddleOCR (兜底, 覆盖 ~10% 扫描件/图片表格)        │
│  • 表格区域检测 + OCR + 结构重建                             │
│  • 耗时: ~3-5s/page (CPU 密集, 按需加载)                    │
└──────────────────────────────────────────────────────────────┘
```

> 详见 [§4.6.1 三级表格提取](#461-三级表格提取)
>
> **演进路线**: Phase 1 使用 pdfplumber → Camelot → PaddleOCR 三级策略。Phase 3 评估 **Docling (Meta, 2024)** 替代 Camelot 层——Docling 针对技术文档（含 Datasheet）布局优化，在复杂表格上可提升 10-20% 提取质量。PaddleOCR 保留为扫描件兜底。

## 2.5 GPTCache 语义缓存

基于 BGE-M3 + Redis 的语义缓存层，拦截语义相似的重复查询（cosine > 0.95），直接返回缓存响应（p99 < 50ms）。

- 缓存 TTL：对话型 1h，对比表型 4h
- 失效策略：新文档 Ingestion 完成时，PUB/SUB 广播清除相关缓存
- 目标命中率：30-50%，减少同等比例的 LLM 调用

> 详见 [§4.10.3 GPTCache 实现](#4103-gptcache-实现)
>
> **演进路线**: Phase 1 使用 GPTCache 库快速验证。Phase 2 计划迁移至**自研语义缓存**（基于 Milvus 相似度检索 + Redis TTL），消除对低维护活跃度外部库的依赖，减少 ~1GB 内存开销。工厂抽象 (`BaseCacheProvider`) 确保迁移零代码改动。

## 2.6 SSO/OIDC 统一认证

```
Frontend ──(1) SSO 登录──▶ FastAPI Gateway
         ◀─(2) 302 Redirect to IdP──
         ──(3) 用户在 IdP 完成认证──▶ IdP (Keycloak/钉钉/飞书)
         ◀─(4) callback?code=xxx──
         ──(5) POST /auth/sso/callback──▶ FastAPI (验证code → 签发内部JWT)
         ◀─(6) {access_token, refresh_token}──
```

| IdP | 协议 | 场景 | 优先级 |
|-----|------|------|--------|
| **Keycloak** | OIDC (标准) | 自建企业 IdP, 推荐 | P0 |
| **钉钉 (DingTalk)** | OAuth2 + 企业内部应用 | 国内企业标配 | P0 |
| **飞书 (Feishu/Lark)** | OAuth2 + 企业自建应用 | 国内科技企业 | P1 |
| **Azure AD** | OIDC (Microsoft) | 外企/混合云 | P2 |

> 详见 [§4.12 安全与认证](#412-安全与认证)

## 2.7 容错与降级

系统采用「外层熔断 + 内层重试」的分层容错架构：

```
┌────────────────────────────────────────┐
│  CircuitBreaker (外层 — 快速失败)       │
│  ┌──────────────────────────────────┐  │
│  │  Tenacity Retry (内层 — 自动恢复) │  │
│  │  • 指数退避 (exponential backoff) │  │
│  │  • 可配置最大重试次数              │  │
│  │  • 按异常类型选择性重试            │  │
│  └──────────────────────────────────┘  │
│  失败次数累计 → 触发熔断 → OPEN 状态    │
└────────────────────────────────────────┘
```

| 组件 | 最大重试 | 退避区间 | 重试条件 |
|------|---------|---------|---------|
| **LLM (LM Studio)** | 2 | 2–15s | `ConnectionError`, `Timeout`, HTTP 502/503 |
| **Embedding (BGE-M3)** | 3 | 0.5–10s | `ConnectionError`, `Timeout` |
| **Milvus** | 4 | 1–30s | `MilvusException`, `grpc.RpcError` |
| **PostgreSQL** | 3 | 0.5–5s | `OperationalError`, `InterfaceError` |

> 详见 [§4.11 并发与容错](#411-并发与容错)

## 2.8 云原生 CI/CD

```
┌────────────┐    ┌────────────┐    ┌────────────┐    ┌──────────────────┐
│  Stage 1   │───▶│  Stage 2   │───▶│  Stage 3   │───▶│   Stage 4        │
│ Lint &     │    │ Docker     │    │ Integration│    │ Deploy           │
│ Unit Test  │    │ Build &    │    │ Tests      │    │ staging: auto    │
│ • ruff     │    │ Security   │    │ • API E2E  │    │ prod: approval   │
│ • mypy     │    │ Scan       │    │ • Milvus   │    │ Phase 1:         │
│ • pytest   │    │ • Trivy    │    │ • PG       │    │  docker-compose  │
│ • GitHub   │    │ • SBOM     │    │ • Redis    │    │ Phase X:         │
│   Scanning │    │            │    │            │    │  helm upgrade    │
└────────────┘    └────────────┘    └────────────┘    └──────────────────┘
```

> 详见 [§5.6 CI/CD 流水线](#56-cicd-流水线)

## 2.9 结构化输出校验

LLM 从 Datasheet 提取芯片参数时，输出 JSON 格式。为防止参数幻觉（如 "Vcc: 999V"），系统采用双层校验：

- **Pydantic Schema 验证** — LLM 输出的 JSON 经 Pydantic 模型严格校验（字段类型、取值范围、必填项），不合规数据触发重试或标记人工审核
- **领域规则约束** — 芯片参数常见值范围校验（如电压 0.8-5.5V、频率 1MHz-2GHz），异常值日志告警

> **Phase 2 演进**: 集成 **Outlines** 等受限解码框架，在 LLM 生成阶段即约束输出符合 JSON Schema，从源头消除格式错误。

## 2.10 RAG 质量评估

系统内建检索质量评估体系，用于量化衡量检索与生成质量、指导模型迁移决策：

- **离线评估指标**: NDCG@10 (检索相关性)、EM/F1 (端到端事实准确率)、延迟百分位 (p50/p99)
- **黄金测试集**: 100+ 条领域 QA 对（人工验证答案），覆盖参数查询/对比/选型/勘误等核心场景
- **自动化基准**: 每次 Embedding/Reranker/LLM 模型切换时自动运行评估，对比前后指标差异

> 详见 [§5.2 集成测试](#52-集成测试)

## 2.11 Token 用量追踪

面向 20 人团队的 LLM 推理成本透明化：

- **Prometheus 指标**: `llm_tokens_total{user_id, model, intent}` — 每请求记录 prompt/completion token 数
- **Grafana 面板**: 按用户/模型/意图类型展示用量趋势
- **告警规则**: 单用户日均 token > 阈值时通知管理员

---
