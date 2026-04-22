# ChipWise Enterprise — 部署指南

**版本**: 1.0 | **更新日期**: 2026-04-13

---

## 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|---|---|---|
| CPU | 8 核 x86-64 | AMD Ryzen AI 395 (12 核, NPU) |
| 内存 | 64 GB | 128 GB |
| 磁盘 | 500 GB SSD | 2 TB NVMe SSD |
| GPU | 无需 | 可选（CUDA 可加速 embedding） |
| 操作系统 | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

参考部署方案使用**单台 AMD Ryzen AI 395 机器（128 GB 内存）**在本地运行所有服务——零数据外泄。

峰值内存分布：
- LM Studio (35B Q5_K_M): ~22 GB
- LM Studio (1.7B 路由模型): ~1.5 GB
- PostgreSQL: ~4 GB (`shared_buffers=2GB`)
- Milvus: ~8 GB（索引常驻内存）
- Redis: ~1 GB
- Celery workers (3): ~6 GB
- FastAPI + Python: ~2 GB
- **峰值总计**: ~45–50 GB（128 GB 提供充足余量）

---

## 软件前置条件

### 1. Python 3.11

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3.11-dev
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Docker & Docker Compose v2

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Re-login, then verify:
docker compose version   # must be >= 2.20
```

### 3. LM Studio

从 [lmstudio.ai](https://lmstudio.ai) 下载并安装到目标机器。

在 LM Studio 中加载以下模型：
- **主推理模型**: `qwen3-35b-q5_k_m`（或同等 ≥30B 模型）
- **路由模型**: `qwen3-1.7b-q5_k_m`（或同等 ≤3B 模型）

在端口 1234 启动 LM Studio 服务：
```
LM Studio → Local Server → Start (port 1234)
```

验证：
```bash
curl http://localhost:1234/v1/models
```

---

## 一键部署

### 步骤 1：克隆与配置

```bash
git clone <repo-url> chipwise-enterprise
cd chipwise-enterprise
cp config/settings.yaml.example config/settings.yaml
```

编辑 `config/settings.yaml` 并设置：
- `llm.primary.model` — LM Studio 中加载的精确模型名称
- `llm.router.model` — 路由模型名称
- `auth.jwt_secret_key` — 使用 `openssl rand -hex 32` 生成

通过环境变量设置密钥（请勿将密钥写入 settings.yaml）：
```bash
export PG_PASSWORD="your-postgres-password"
export REDIS_PASSWORD="your-redis-password"
export JWT_SECRET_KEY="$(openssl rand -hex 32)"
export SSO_CLIENT_SECRET="your-oauth-client-secret"   # only if using SSO
```

### 步骤 2：启动基础设施

```bash
docker compose up -d
```

此命令将启动：
- PostgreSQL :5432
- Milvus :19530（含 etcd 和 MinIO）
- Redis :6379
- BGE-M3 embedding 服务 :8001
- bce-reranker 服务 :8002

验证所有容器健康状态：
```bash
docker compose ps
```

### 步骤 3：初始化数据库

```bash
source .venv/bin/activate

# PostgreSQL schema
alembic upgrade head
# or: python scripts/init_db.py

# Milvus collections (dense + sparse vectors)
python scripts/init_milvus.py

# Kùzu knowledge graph (embedded, no Docker)
python scripts/init_kuzu.py
```

### 步骤 4：启动应用服务

```bash
# FastAPI gateway
uvicorn src.api.main:app --host 0.0.0.0 --port 8080 &

# Celery workers
celery -A src.ingestion.tasks worker -Q default,embedding -c 1 -n worker1@%h &
celery -A src.ingestion.tasks worker -Q heavy -c 1 -n worker2@%h &
celery -A src.ingestion.tasks worker -Q crawler -c 1 -n worker3@%h &
celery -A src.ingestion.tasks beat --loglevel=info &

# Gradio frontend
python frontend/gradio_app.py &
```

或使用便捷脚本：
```bash
bash scripts/start_services.sh
```

### 步骤 5：验证

```bash
python scripts/healthcheck.py
# Expected: All 7 services healthy

curl http://localhost:8080/health
# Expected: {"status": "ok", "version": "1.0.0"}
```

前端访问地址：`http://localhost:7860`
API 文档地址：`http://localhost:8080/docs`

---

## settings.yaml 参考

完整 schema 定义见 `docs/ENTERPRISE_DEV_SPEC.md` §7.1。关键配置段如下：

```yaml
llm:
  primary:
    provider: openai_compatible
    base_url: "http://localhost:1234/v1"
    model: "qwen3-35b-q5_k_m"    # must match LM Studio loaded model name
    api_key: "lm-studio"          # arbitrary string for LM Studio
    timeout: 120
    max_tokens: 8192
  router:
    provider: openai_compatible
    base_url: "http://localhost:1234/v1"
    model: "qwen3-1.7b-q5_k_m"
    api_key: "lm-studio"
    timeout: 30
    max_tokens: 512

embedding:
  provider: bgem3
  base_url: "http://localhost:8001"
  model: "BAAI/bge-m3"

reranker:
  provider: bce
  base_url: "http://localhost:8002"
  model: "maidalun1020/bce-reranker-base_v1"
  top_k: 5

vector_store:
  provider: milvus
  host: localhost
  port: 19530
  collection_name: chipwise_chunks

graph_store:
  provider: kuzu
  data_dir: "data/kuzu"

database:
  host: localhost
  port: 5432
  name: chipwise
  user: chipwise
  # password: set PG_PASSWORD env var

redis:
  host: localhost
  port: 6379
  # password: set REDIS_PASSWORD env var

agent:
  max_iterations: 5
  max_tokens: 8192

auth:
  jwt_algorithm: RS256
  jwt_expiry_minutes: 30
  cors_origins:
    - "http://localhost:7860"
    - "http://localhost:3000"
  # SSO configuration below (optional)
  sso:
    enabled: false
    provider: keycloak            # keycloak | dingtalk | feishu
```

---

## SSO 配置

### Keycloak

1. 在 Keycloak 管理控制台中创建 realm `chipwise`
2. 创建客户端 `chipwise`，设置如下：
   - 客户端类型：OpenID Connect
   - 重定向 URI：`http://your-domain:8080/api/v1/auth/sso/callback`
   - 客户端认证：开启
3. 将客户端密钥复制到 `SSO_CLIENT_SECRET` 环境变量
4. 更新 `config/settings.yaml`：

```yaml
auth:
  sso:
    enabled: true
    provider: keycloak
    client_id: chipwise
    redirect_uri: "http://your-domain:8080/api/v1/auth/sso/callback"
    authorization_endpoint: "https://keycloak-host/realms/chipwise/protocol/openid-connect/auth"
    token_endpoint: "https://keycloak-host/realms/chipwise/protocol/openid-connect/token"
    jwks_uri: "https://keycloak-host/realms/chipwise/protocol/openid-connect/certs"
    issuer: "https://keycloak-host/realms/chipwise"
```

### DingTalk (钉钉)

1. 在钉钉开发者控制台创建自建应用
2. 启用"钉钉登录"功能，并将回调 URL 设置为 `http://your-domain:8080/api/v1/auth/sso/callback`
3. 更新 `config/settings.yaml`：

```yaml
auth:
  sso:
    enabled: true
    provider: dingtalk
    client_id: "<AppId>"
    redirect_uri: "http://your-domain:8080/api/v1/auth/sso/callback"
```

### Feishu (飞书)

1. 在飞书开放平台创建自建应用
2. 启用"网页应用"能力并设置重定向 URL
3. 更新 `config/settings.yaml`：

```yaml
auth:
  sso:
    enabled: true
    provider: feishu
    client_id: "<AppId>"
    redirect_uri: "http://your-domain:8080/api/v1/auth/sso/callback"
```

---

## 监控套件（可选）

```bash
docker compose -f docker-compose.monitoring.yml up -d
```

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`（首次登录使用 admin/admin）

`chipwise-overview` 仪表盘已自动预置，包含以下面板：
- 服务健康状态、请求 QPS、LLM Token 用量、P95 延迟、缓存命中率、数据摄取队列深度

---

## 生产环境检查清单

- [ ] `settings.yaml` 中设置 `debug: false`
- [ ] 所有密钥通过环境变量设置（不写入配置文件）
- [ ] LM Studio 已运行且模型已加载
- [ ] 全部 7 个服务通过 `python scripts/healthcheck.py` 检查
- [ ] 已通过 Nginx 反向代理配置 HTTPS
- [ ] 防火墙：端口 1234（LM Studio）禁止外部访问
- [ ] 已配置每日备份定时任务（参见 `docs/OPERATIONS.md`）
- [ ] 已为 `logs/` 目录配置日志轮转
