# 3. 技术选型

## 3.1 硬件平台

| 资源 | 规格 | 备注 |
|------|------|------|
| **CPU** | AMD Ryzen AI 395 | Zen 5 架构, 16C/32T (预估), 集成 XDNA 2 NPU |
| **NPU** | AMD XDNA 2 | 50+ TOPS INT8, 可用于未来加速推理 |
| **iGPU** | AMD Radeon 890M | RDNA 3.5, 16 CU, 用于 LLM decode 阶段加速 |
| **内存** | 128 GB DDR5-5600 | 双通道, 统一内存架构 (CPU/NPU/iGPU 共享) |
| **存储** | 2 TB NVMe SSD | Gen4 x4, 用于 Milvus mmap 和 PG WAL |
| **操作系统** | Windows 11 (WSL2) 或 Ubuntu 22.04 | 推荐 Windows 以兼容 LM Studio 原生支持 |

**内存预算分配** (128 GB)：

| 组件 | 分配 | 说明 |
|------|------|------|
| OS + 系统服务 | 4 GB | Windows/Linux 基础 |
| 主推理模型 (LM Studio, 如 35B Q5_K_M) | 24 GB | 多模态推理/生成/Tool Calling, NPU offload |
| 轻量路由模型 (LM Studio, 如 1.7B Q5_K_M) | 2 GB | 查询改写/意图分类/简单路由, 低延迟 |
| BGE-M3 (FastAPI :8001) | 2.5 GB | 常驻, batch 推理 |
| bce-reranker (FastAPI :8002) | 1.5 GB | 常驻, on-demand |
| Milvus Standalone (Docker) | 16 GB | HNSW 索引 + mmap |
| PostgreSQL 15 (Docker) | 4 GB | shared_buffers=2GB |
| Redis 7 (Docker) | 3 GB | Cache + Broker + Session + RateLimit |
| Celery Workers ×3 | 6 GB | 2GB/worker, 含 PaddleOCR on-demand |
| FastAPI Application | 2 GB | 主应用 + 请求处理 |
| PaddleOCR (按需加载) | 3 GB | 仅 Ingestion 时加载 |
| Playwright (爬虫, 按需) | 1 GB | headless Chromium |
| Kùzu Graph DB (嵌入式) | 2 GB | 进程内, mmap 模式 |
| **已分配合计** | **~71 GB** | |
| **剩余 (OS Cache / 弹性)** | **~57 GB** | Milvus mmap, PG cache, burst 负载缓冲 |

> **关键洞察**: 128GB 内存充裕。主推理模型 (35B 级) 在单机上有效并发约 2 路，但轻量路由模型 (1-3B) 可独立处理查询改写和意图分类，有效并发 10+ 路，大幅降低主模型负载。57GB 剩余空间可被操作系统用作文件缓存，显著加速 Milvus mmap 读取和 PostgreSQL 查询。实际模型大小可通过 LM Studio 灵活调整——128GB RAM 可承载远超 14B 的模型。
>
> **峰值风险提示**: 当 Celery Ingestion (PaddleOCR 3GB) 与用户高并发查询 (10+ 用户) 同时发生时，实际内存占用可达 ~110-120GB。**缓解策略**: (1) Celery Worker 实现内存感知暂停——当系统内存利用率 > 85% 时暂停 Ingestion 任务；(2) `worker_prefetch_multiplier=1` 防止任务囤积；(3) LLM 信号量饱和时优先用户请求、延迟离线任务。

## 3.2 LLM 推理

LM Studio 在 AMD Ryzen AI 395 上支持同时加载多个模型，通过统一的 OpenAI 兼容 API 对外提供服务。系统采用双模型架构：

| 阶段 | 硬件 | 说明 |
|------|------|------|
| **Prefill** (prompt 处理) | NPU (XDNA 2) | 批量 token 处理, NPU 的矩阵运算优势 |
| **Decode** (token 生成) | iGPU (Radeon 890M) | 逐 token 自回归, iGPU 更适合低延迟串行 |
| **KV Cache** | DDR5 统一内存 | NPU/iGPU 共享内存, 零拷贝 |

LM Studio 对外暴露 **OpenAI 兼容 API** (`http://localhost:1234/v1`)，在 `BaseLLM` 工厂中以 `openai_compatible` 提供者注册：

```yaml
# config/settings.yaml — 多模型配置
llm:
  # 主推理模型: 负责核心推理、生成、Tool Calling、多模态理解
  primary:
    provider: openai_compatible
    base_url: "http://localhost:1234/v1"
    model: "qwen3-35b-q5_k_m"          # 示例; 可替换为任意 LM Studio 已加载模型
    api_key: "lm-studio"
    max_tokens: 4096
    temperature: 0.1
    timeout: 90
    max_concurrent: 2
  # 轻量路由模型: 查询改写、意图分类、简单路由决策
  router:
    provider: openai_compatible
    base_url: "http://localhost:1234/v1"
    model: "qwen3-1.7b-q5_k_m"         # 示例; 1-3B 级模型即可
    api_key: "lm-studio"
    max_tokens: 256
    temperature: 0.0
    timeout: 15
    max_concurrent: 10
```

> **模型灵活性**: LM Studio 支持加载任意 GGUF 格式模型。上述 `qwen3-35b` 和 `qwen3-1.7b` 仅为示例。
> AMD Ryzen AI 395 配合 128GB DDR5 内存可轻松运行 35B+ 级别模型。如选择多模态模型 (如 Gemma 4 27B)，
> 系统可直接对 datasheet 中的原理图/引脚图进行视觉理解，无需 BaseVisionLLM 扩展。

## 3.3 Embedding & Rerank

- **Embedding**: BGE-M3 (BAAI/bge-m3, 1024-dim) 常驻 FastAPI 微服务 (:8001)，同时产出 dense + sparse 向量
- **Rerank**: bce-reranker-base_v1 常驻 FastAPI 微服务 (:8002)，可通过 `enabled: false` 跳过

> **演进路线**: Phase 1 使用 BGE-M3 + bce-reranker-v1（中文优化，生产验证充分）。Phase 2 评估迁移至 **Jina v3** (Embedding, 2025 MTEB SOTA, 技术文本精度更优) 和 **jina-reranker-v2** (Rerank, 跨语言能力更强，适配英文 Datasheet 场景)。工厂抽象 (`EmbeddingFactory` / `RerankerFactory`) 确保热切换零代码改动。

## 3.4 数据存储

| 存储引擎 | 用途 | 选型理由 |
|----------|------|---------|
| **PostgreSQL 15+** | 关系数据 (芯片/参数/用户/BOM/勘误) | 成熟 ACID, 丰富索引, Alembic 迁移 |
| **Milvus 2.4+** | 向量检索 (Dense+Sparse+RRF) | 原生混合检索, 可扩展至分布式集群 |
| **Redis 7** | 缓存/队列/会话/限流 | 多数据结构, PUB/SUB, Celery Broker |
| **Kùzu** | 知识图谱 (芯片/参数/替代/勘误) | 嵌入式零运维, openCypher, mmap 低开销 |

## 3.5 任务队列与爬虫

- **Celery + Redis**: 异步分布式任务队列，3 Worker 分别处理默认/重任务(PaddleOCR)/爬虫队列
- **Playwright**: 无头浏览器爬虫，定时抓取 ST/TI/NXP 官网 Datasheet 更新

> **演进路线**: Phase 1 使用 Celery（生产验证充分，团队熟悉）。Phase 2 评估 **Dramatiq**（内存开销降低 ~40%）或 **Huey**（Python 原生，配置更简洁）。当前 Celery 3 Worker × 2GB = 6GB 内存占用偏重，迁移后可释放 ~3GB 用于 Milvus 或 PostgreSQL。

## 3.6 前端框架

- **Phase 1 (MVP)**: Gradio (:7860)，快速验证
- **Phase 2 (Production)**: Vue3 + Element Plus，企业级前端

## 3.7 DevOps 工具链

| 工具 | 用途 |
|------|------|
| **Docker Compose** | 本地开发 / 集成测试 / Phase 1 生产部署 |
| **Helm Charts** | K8s 生产/预发布部署 **(Phase X, 单机阶段不需要)** |
| **GitHub Actions** | CI/CD 四阶段流水线 |
| **Ruff + mypy** | 代码质量 (Lint + 类型检查, Phase 1 起) |
| **GitHub Code Scanning** | 安全分析 (免费, 集成 Actions, Phase 1 起) |
| **SonarQube** | 深度代码质量分析 **(Phase X 可选, 团队 >50 人时引入)** |
| **Trivy** | 容器镜像安全扫描 |
| **Prometheus + Grafana** | 监控与告警 |

## 3.8 服务端口清单

| 服务 | 端口 | 协议 | 说明 |
|------|------|------|------|
| FastAPI Gateway | 8080 | HTTP/WS | 主 API 入口 |
| LM Studio | 1234 | HTTP | OpenAI 兼容 LLM API |
| BGE-M3 Service | 8001 | HTTP | Embedding 微服务 |
| bce-reranker Service | 8002 | HTTP | Rerank 微服务 |
| PostgreSQL | 5432 | TCP | 关系数据库 |
| Milvus | 19530 | gRPC | 向量数据库 |
| Milvus Metrics | 9091 | HTTP | Milvus 健康检查 |
| Redis | 6379 | TCP | 缓存/队列 |
| Kùzu Graph DB | N/A | 嵌入式 | 进程内图数据库 (数据目录: `data/kuzu/`) |
| Gradio Frontend | 7860 | HTTP | MVP 前端 |
| Celery Flower | 5555 | HTTP | 任务监控 (可选) |

---
