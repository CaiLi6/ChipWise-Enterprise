# 7. 附录

## 7.1 settings.yaml 完整参考

> **注意**: `config/settings.yaml` 文件尚未创建。以下为完整参考模板，将在开发阶段 Phase 1A Task 1A3 落地为实际配置文件。

```yaml
# ============================================================
# ChipWise Enterprise Configuration
# ============================================================

# --- LLM (LM Studio 多模型配置) ---
llm:
  # 主推理模型: 核心推理、生成、Tool Calling
  # 模型名称仅为示例，可替换为 LM Studio 已加载的任意 GGUF 模型
  primary:
    provider: openai_compatible
    base_url: "http://localhost:1234/v1"
    model: "qwen3-35b-q5_k_m"
    api_key: "lm-studio"
    max_tokens: 4096
    temperature: 0.1
    timeout: 90
    max_concurrent: 2
  # 轻量路由模型: 查询改写、意图分类、路由决策
  router:
    provider: openai_compatible
    base_url: "http://localhost:1234/v1"
    model: "qwen3-1.7b-q5_k_m"
    api_key: "lm-studio"
    max_tokens: 256
    temperature: 0.0
    timeout: 15
    max_concurrent: 10

# --- Embedding (BGE-M3 FastAPI 微服务) ---
embedding:
  provider: fastapi_remote
  base_url: "http://localhost:8001"
  model: "BAAI/bge-m3"
  dim: 1024
  batch_size: 32
  timeout: 30

# --- Reranker (bce-reranker FastAPI 微服务) ---
rerank:
  provider: fastapi_remote
  base_url: "http://localhost:8002"
  model: "maidalun1020/bce-reranker-base_v1"
  top_k: 10
  timeout: 10
  enabled: true

# --- Vector Store ---
vector_store:
  backend: milvus                    # milvus | milvus_cluster | qdrant
  milvus:
    host: "localhost"
    port: 19530
    collection_name: "datasheet_chunks"
    consistency_level: "Session"
  milvus_cluster:
    uri: "http://milvus-proxy.chipwise-prod:19530"
    consistency_level: "Strong"
    replica_number: 2
  qdrant:
    url: "http://qdrant.chipwise-prod:6333"
    replication_factor: 2
    shard_number: 3

# --- PostgreSQL ---
database:
  host: "localhost"
  port: 5432
  database: "chipwise"
  user: "chipwise"
  password: "${PG_PASSWORD}"
  pool_size: 10
  max_overflow: 5

# --- Redis ---
redis:
  host: "localhost"
  port: 6379
  db: 0
  celery_db: 1
  password: "${REDIS_PASSWORD}"

# --- Retrieval ---
retrieval:
  mode: hybrid
  top_k_search: 30
  top_k_rerank: 10
  rrf_k: 60

# --- Semantic Cache (GPTCache) ---
cache:
  enabled: true
  similarity_threshold: 0.95
  ttl_conversational: 3600
  ttl_comparison: 14400

# --- Rate Limiting ---
rate_limit:
  per_user_per_minute: 30
  per_user_per_hour: 500
  global_primary_llm_concurrent: 2
  global_router_llm_concurrent: 10

# --- Agent Orchestrator (v3.0) ---
agent:
  max_iterations: 5
  max_total_tokens: 8192
  parallel_tool_calls: true
  temperature: 0.1          # 主推理模型; 路由模型固定 temperature=0
  tool_timeout: 30.0

# --- Graph Store (v3.0) ---
graph_store:
  backend: kuzu
  kuzu:
    db_path: "data/kuzu"
  neo4j:
    uri: "bolt://localhost:7687"
    user: "neo4j"
    password: "${NEO4J_PASSWORD}"

# --- Ingestion ---
ingestion:
  pdf_extractor:
    tier1: pdfplumber
    tier2: camelot
    tier3: paddleocr
  chunking:
    chunk_size: 1000
    chunk_overlap: 200
    separator: ["\n\n", "\n", ". ", " "]
  crawler:
    schedule: "0 2 * * *"
    max_per_run: 50
  watchdog:
    paths: ["//fileserver/datasheets/"]
    debounce_seconds: 5
    file_types: [".pdf"]

# --- Auth (SSO/OIDC) ---
auth:
  mode: sso                           # sso | local
  sso:
    provider: keycloak
    issuer: "https://keycloak.company.com/realms/chipwise"
    client_id: "chipwise-enterprise"
    client_secret: "${SSO_CLIENT_SECRET}"
    redirect_uri: "https://chipwise.company.com/api/v1/auth/sso/callback"
    scopes: ["openid", "profile", "email", "groups"]
    group_role_mapping:
      "chipwise-admin": "admin"
      "chipwise-engineers": "user"
      "chipwise-viewers": "viewer"
      "default": "viewer"
  jwt:
    algorithm: "RS256"
    private_key_path: "/run/secrets/jwt-private.pem"
    public_key_path: "/run/secrets/jwt-public.pem"
    access_token_expire_minutes: 30
    refresh_token_expire_days: 7
  local_fallback:
    enabled: true
    jwt_secret: "${JWT_SECRET_KEY}"

# --- Resilience ---
resilience:
  circuit_breaker:
    failure_threshold: 5
    recovery_timeout: 30
    success_threshold: 2
  tenacity:
    llm:       { max_attempts: 3, min_wait: 2, max_wait: 15 }
    embedding: { max_attempts: 4, min_wait: 0.5, max_wait: 10 }
    reranker:  { max_attempts: 4, min_wait: 0.5, max_wait: 10 }
    milvus:    { max_attempts: 5, min_wait: 1, max_wait: 30 }
    postgres:  { max_attempts: 4, min_wait: 0.5, max_wait: 5 }
    redis:     { max_attempts: 4, min_wait: 0.2, max_wait: 2 }
    crawler:   { max_attempts: 6, min_wait: 2, max_wait: 60 }

# --- Observability ---
observability:
  trace_log_file: "./logs/traces.jsonl"
  app_log_file: "./logs/app.log"
  log_level: "INFO"
  celery_log_file: "./logs/celery.log"

# --- Frontend ---
frontend:
  type: gradio
  port: 7860
  share: false
```

> **迁移说明**: `llm` 配置从单层结构改为 `llm.primary` + `llm.router` 双层结构。
> `LLMFactory.create(settings)` 需相应更新为 `LLMFactory.create(settings, role="primary"|"router")`。
> 若仅加载单个模型，可将 `llm.router` 指向与 `llm.primary` 相同的模型，系统仍正常运行。

## 7.2 API 接口目录

> FastAPI 启动后自动生成 OpenAPI 3.0 规范，访问 `http://localhost:8080/docs` 获取 Swagger UI。以下表格为规划阶段的接口目录，待代码实现后以自动生成的 OpenAPI 规范为准。

### 认证相关

| Method | Path | 说明 | 权限 |
|--------|------|------|------|
| GET | `/api/v1/auth/sso/authorize` | 发起 SSO 登录 | Public |
| GET | `/api/v1/auth/sso/callback` | IdP 回调 | Public |
| POST | `/api/v1/auth/sso/logout` | SSO 登出 | Authenticated |
| POST | `/api/v1/auth/login` | 本地密码登录 (降级) | Public |
| POST | `/api/v1/auth/refresh` | 刷新 Token | Authenticated |
| GET | `/api/v1/auth/userinfo` | 当前用户信息 | Authenticated |

### 查询与检索

| Method | Path | 说明 | 权限 |
|--------|------|------|------|
| POST | `/api/v1/query` | 对话式查询 | user+ |
| POST | `/api/v1/query/stream` | SSE 流式查询 | user+ |
| POST | `/api/v1/compare` | 芯片对比 | user+ |
| POST | `/api/v1/test-cases` | 测试用例生成 | user+ |
| POST | `/api/v1/selection` | 芯片选型推荐 | user+ |
| POST | `/api/v1/design-check` | 设计规则检查 | user+ |

### BOM 审查

| Method | Path | 说明 | 权限 |
|--------|------|------|------|
| POST | `/api/v1/bom/upload` | 上传 BOM Excel | user+ |
| GET | `/api/v1/bom/{bom_id}` | 获取审查结果 | user+ |
| GET | `/api/v1/bom/{bom_id}/export` | 导出标注 Excel | user+ |

### 文档管理

| Method | Path | 说明 | 权限 |
|--------|------|------|------|
| POST | `/api/v1/documents/upload` | 上传文档 | user+ |
| GET | `/api/v1/documents` | 文档列表 | viewer+ |
| GET | `/api/v1/documents/{id}` | 文档详情 | viewer+ |
| DELETE | `/api/v1/documents/{id}` | 删除文档 | admin |

### 知识沉淀

| Method | Path | 说明 | 权限 |
|--------|------|------|------|
| POST | `/api/v1/knowledge/notes` | 创建知识笔记 | user+ |
| GET | `/api/v1/knowledge/notes` | 笔记列表 | viewer+ |
| PUT | `/api/v1/knowledge/notes/{id}` | 更新笔记 | owner/admin |
| DELETE | `/api/v1/knowledge/notes/{id}` | 删除笔记 | owner/admin |

### 芯片数据

| Method | Path | 说明 | 权限 |
|--------|------|------|------|
| GET | `/api/v1/chips` | 芯片列表 | viewer+ |
| GET | `/api/v1/chips/{id}` | 芯片详情 + 参数 | viewer+ |
| GET | `/api/v1/chips/{id}/errata` | 芯片关联勘误 | viewer+ |
| GET | `/api/v1/chips/{id}/alternatives` | 芯片替代料 | viewer+ |

### 任务与系统

| Method | Path | 说明 | 权限 |
|--------|------|------|------|
| GET | `/api/v1/tasks/{id}` | 任务状态查询 | user+ |
| GET | `/health` | 健康检查 | Public |
| GET | `/readiness` | 就绪检查 | Public |
| GET | `/api/v1/admin/stats` | 系统统计 | admin |

### 报告生成

| Method | Path | 说明 | 权限 |
|--------|------|------|------|
| POST | `/api/v1/reports/chip-evaluation` | 芯片评估报告 | user+ |
| POST | `/api/v1/reports/selection-report` | 选型推荐报告 | user+ |
| GET | `/api/v1/reports/{id}/download` | 下载报告 | user+ |

## 7.3 数据契约定义

```python
# src/core/types.py

@dataclass
class Document:
    """源文档, 对应一个 PDF 文件"""
    id: str
    text: str
    metadata: dict = field(default_factory=dict)

@dataclass
class Chunk:
    """文本分片"""
    id: str                          # Stable ID: {doc_hash}_{index:04d}_{content_hash}
    text: str
    metadata: dict = field(default_factory=dict)

@dataclass
class ChunkRecord:
    """带向量的分片记录"""
    chunk: Chunk
    dense_vector: list[float]        # 1024-dim (BGE-M3)
    sparse_vector: dict              # {token_id: weight}

@dataclass
class RetrievalResult:
    """检索结果"""
    chunk_id: str
    score: float
    rank: int
    retriever_method: str            # "dense" | "sparse" | "hybrid" | "sql"
    content: str = ""
    metadata: dict = field(default_factory=dict)

@dataclass
class ProcessedQuery:
    """处理后的查询"""
    original_text: str
    rewritten_text: str
    intent: str
    params: dict = field(default_factory=dict)
    metadata_filters: dict = field(default_factory=dict)
    user_id: Optional[int] = None
    session_id: Optional[str] = None

@dataclass
class PipelineResult:
    """管线执行结果"""
    content: str
    pipeline: str
    citations: list[dict] = field(default_factory=list)
    comparison_table: Optional[dict] = None
    export_path: Optional[str] = None

@dataclass
class Citation:
    """Datasheet 来源引用"""
    source_document: str
    part_number: str
    page: Optional[int] = None
    section: Optional[str] = None
    doc_type: str = "datasheet"

@dataclass
class ChipParameter:
    """结构化芯片参数"""
    name: str
    category: str
    min_value: Optional[float] = None
    typ_value: Optional[float] = None
    max_value: Optional[float] = None
    unit: str = ""
    condition: str = ""
```

## 7.4 术语表

| 术语 | 说明 |
|------|------|
| **RAG** | Retrieval-Augmented Generation, 检索增强生成 |
| **BGE-M3** | BAAI General Embedding - Multi-lingual Multi-granularity Multi-functionality |
| **RRF** | Reciprocal Rank Fusion, 倒数排名融合算法 |
| **HNSW** | Hierarchical Navigable Small World, 近似最近邻搜索算法 |
| **GPTCache** | LLM 响应语义缓存框架 |
| **LM Studio** | 跨平台本地 LLM 推理平台, 提供 OpenAI 兼容 API (localhost:1234) |
| **NPU** | Neural Processing Unit, 神经网络处理单元 |
| **iGPU** | Integrated GPU, 集成显卡 |
| **XDNA 2** | AMD 第二代 AI 引擎架构 |
| **Celery** | Python 分布式异步任务队列框架 |
| **Milvus** | 开源向量数据库, 支持混合检索 |
| **EOL** | End of Life, 产品停产 |
| **NRND** | Not Recommended for New Designs, 不推荐用于新设计 |
| **BOM** | Bill of Materials, 物料清单 |
| **Errata** | 勘误表, 芯片已知问题和修正 |
| **Application Note** | 应用笔记, 厂商提供的设计参考文档 |
| **LSH** | Locality-Sensitive Hashing, 局部敏感哈希 |
| **JWT** | JSON Web Token, 无状态认证令牌 |
| **RBAC** | Role-Based Access Control, 基于角色的访问控制 |
| **SSE** | Server-Sent Events, 服务器推送事件 |
| **SSO** | Single Sign-On, 单点登录 |
| **OIDC** | OpenID Connect, 基于 OAuth2 的身份认证协议 |
| **OAuth2** | 开放授权框架 |
| **Keycloak** | 开源 IAM 平台, 支持 OIDC/SAML/LDAP |
| **IdP** | Identity Provider, 身份提供商 |
| **JWKS** | JSON Web Key Set, 公钥集合端点 |
| **JIT Provisioning** | Just-In-Time Provisioning, 首次登录自动创建用户 |
| **RS256** | RSA SHA-256, 非对称 JWT 签名算法 |
| **Tenacity** | Python 重试库, 支持指数退避等策略 |
| **Helm** | K8s 包管理器 |
| **K8s** | Kubernetes, 容器编排平台 |
| **HPA** | Horizontal Pod Autoscaler |
| **PDB** | Pod Disruption Budget |
| **SonarQube** | 代码质量与安全分析平台 **(Phase X 可选)** |
| **Trivy** | 开源容器安全扫描器 |
| **SARIF** | Static Analysis Results Interchange Format |

---

*— End of Document —*

*ChipWise Enterprise Architecture Specification v5.0*
*Approved by CTO Office, 2026-04-08*
