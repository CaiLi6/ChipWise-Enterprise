# 极摩客首次部署 Checklist

> **这份文档是干什么的**：把本地电脑的项目 `git clone` 到极摩客之后，照着这份清单一步步做完就能跑起来。本地电脑全程没有 LM Studio，所有涉及 LLM 的路径在本地都是 mock 的 —— 极摩客是**第一次用真实 LM Studio 验证整条链路**，所以 Phase 8 起一切可能出错的地方都重点标注了。

> **给 Claude Code 的提示**：如果你是在极摩客首次启动的 Claude Code 会话，用户大概率是刚 `git clone` 完。主动检查 `.env` 是否存在、LM Studio 是否在跑、Docker 服务是否启动，然后从 Phase 0 开始带用户过一遍。遇到任何 Phase 卡住就 root-cause 分析，不要绕过。

---

## Phase 0 — Pre-flight 环境体检

目的：先确认基座 OK，再动任何配置。

- [ ] OS 版本 ≥ Ubuntu 22.04 / 同等发行版
- [ ] `docker --version` ≥ 24，`docker compose version` ≥ v2.20
- [ ] `python3 --version` ≥ 3.10（建议 3.12）
- [ ] `node --version` ≥ 20
- [ ] 硬件：Ryzen AI 395 / 128GB RAM / 足够磁盘（datasheet + Milvus 建议预留 100GB+）
- [ ] LM Studio 已安装、能打开、能 load 模型
- [ ] 网络：`curl http://localhost:1234/v1/models`（LM Studio 默认端口）能通

**兜底**：任何一项不满足，**不要继续**，先修环境。

---

## Phase 1 — Secrets & 配置

```bash
cd ~/ChipWise-Enterprise  # 或 clone 到的路径
cp .env.example .env
```

**编辑 `.env`**，填入：
- `PG_PASSWORD` — 给 PostgreSQL 设强密码（随机 24 字符以上）
- `REDIS_PASSWORD` — 同上
- `JWT_SECRET_KEY` — `openssl rand -hex 32`
- `SSO_CLIENT_SECRET` — 从 Keycloak/DingTalk/Feishu 管理后台拿
- `VITE_API_BASE_URL` — 极摩客局域网访问地址（如 `http://<极摩客IP>:8080`）
- `GF_SECURITY_ADMIN_PASSWORD` — Grafana admin 密码

**生成 JWT RSA 密钥对**：
```bash
sudo mkdir -p /run/secrets
sudo openssl genrsa -out /run/secrets/jwt-private.pem 2048
sudo openssl rsa -in /run/secrets/jwt-private.pem -pubout -out /run/secrets/jwt-public.pem
sudo chown $USER:$USER /run/secrets/jwt-*.pem
sudo chmod 600 /run/secrets/jwt-private.pem
```

**核对 `config/settings.yaml`**：
- `llm.primary.model` 和 `llm.router.model` 名字**必须**和 LM Studio 里 load 的模型 ID 一致
- `llm.primary.base_url` / `llm.router.base_url` 是 `http://localhost:1234/v1`（如果 LM Studio 和 app 在同一台机器）
- `embedding.base_url` / `rerank.base_url` 指向容器服务名（docker 网络内）或 localhost（裸机跑）

---

## Phase 2 — LM Studio 模型加载

在 LM Studio UI 里：
- [ ] Load `qwen3-35b-q5_k_m`（primary，大模型）
- [ ] Load `qwen3-1.7b-q5_k_m`(router，小模型)
- [ ] Enable server mode，端口 `1234`

验证：
```bash
curl -s http://localhost:1234/v1/models | jq '.data[].id'
# 应返回两个 model id，和 settings.yaml 里完全一致
```

**小心**：`llm.primary.max_concurrent=2` 是给 35B 模型设计的限流，不要改大否则 OOM。

---

## Phase 3 — 基础设施启动

```bash
# PostgreSQL + Redis + Milvus
docker compose up -d postgres redis milvus

# 等健康
docker compose ps
# 所有 service 的 STATUS 都应该是 "healthy" 或 "Up N seconds"

# Schema
pip install -e ".[dev]"
alembic upgrade head
python scripts/init_milvus.py
python scripts/init_kuzu.py

# 可选：种子数据
psql -h localhost -U chipwise -d chipwise -f tests/fixtures/seed_chips.sql
```

**验证**：`python scripts/healthcheck.py` 应全绿（除了下面 Phase 4 才启动的服务）。

---

## Phase 4 — 模型微服务

```bash
docker compose -f docker-compose.services.yml up -d
# BGE-M3 → :8001, bce-reranker → :8002

# 等 30-60s（首次启动要拉模型权重）
curl http://localhost:8001/health
curl http://localhost:8002/health
```

---

## Phase 5 — 应用镜像构建

```bash
docker build -t chipwise-api:local .
docker build -t chipwise-celery:local -f Dockerfile.celery .
docker build -t chipwise-web:local -f frontend/web/Dockerfile frontend/web

docker images | grep chipwise
# 应看到 3 个镜像
```

**兜底**：如果 `requirements.txt` 里的某个包（pymilvus、paddleocr、camelot）编译失败，补 apt 依赖到 `Dockerfile` 的 builder 阶段。

---

## Phase 6 — 后端 + Worker 启动

**两种模式二选一**：

**A. 开发模式**（分进程，方便 debug）：
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8080 &
celery -A src.ingestion.tasks worker -Q default,embedding -c 1 -n w1@%h &
celery -A src.ingestion.tasks worker -Q heavy -c 1 -n w2@%h &       # PaddleOCR
celery -A src.ingestion.tasks worker -Q crawler -c 1 -n w3@%h &
celery -A src.ingestion.tasks beat --loglevel=info &
```

**B. 生产模式**（compose 编排）：
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**验证**：
```bash
curl http://localhost:8080/readiness | jq
# 应看到 pg / redis / milvus / embedding / reranker / lmstudio_primary / lmstudio_router 全部 healthy
```

---

## Phase 7 — 监控栈

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d prometheus grafana
```

- **Prometheus**：`http://<极摩客IP>:9090` → Status → Targets，所有 target 应 `UP`
- **Grafana**：`http://<极摩客IP>:3001` → 登录（用户 admin，密码从 `.env`）→ Dashboards 应看到 4 个：
  - chipwise-overview
  - llm-performance
  - retrieval-quality
  - ingestion-pipeline
- **Alert rules**：`http://<极摩客IP>:9090/alerts` → 应看到 9 条规则，状态 `inactive` 或 `pending`

---

## Phase 8 — 测试全量回归（与本地 diff）

```bash
# 单测（本地已绿：706 pass）
pytest -q -m unit

# 本地 Docker 可跑的集成（本地已绿）
pytest -q -m integration_nollm

# 需要 LM Studio 的真集成 —— 本地从未跑过！
pytest -q -m integration
# 这是关键验证点。可能暴露的问题：
# - LLM 返回格式和 mock 不一致导致 parser 失败
# - 真实 token 计数溢出 TokenBudget(8192)
# - Prompt 模板和 qwen3-35b 的指令遵循能力不匹配
# - Embedding 向量维度不匹配（理论上 1024 固定）
# - Reranker 返回分数分布异常

# E2E（本地从未跑过）
pytest -q -m e2e
```

**遇到 fail 不要慌**：
1. 记录到 `docs/DEPLOYMENT_ISSUES.md`（没有就现建）
2. 按 fail 模块分类：`llm/` / `retrieval/` / `agent/` / `api/`
3. 每类挑 1 个典型 fail 深挖 root cause
4. 常见问题见下面 Phase 12 "已知风险"

**已知遗留**（本地已发现，部署前最好先修）：
- `tests/security/test_owasp_checklist.py` 3 个 fail（Phase 6 引入）：
  - `test_password_hashed_on_register`
  - `test_duplicate_registration_returns_409`
  - `test_token_response_has_no_password`
- Playwright mock 模式下有失败用例（Phase 11 期间发现未修）

---

## Phase 9 — 前端真实联调

```bash
cd frontend/web
npm ci
npm run build
npm run preview &
# 预览 :4173
```

或用生产镜像：
```bash
docker run --rm -d -p 80:80 --name chipwise-web chipwise-web:local
# 浏览器访问 http://<极摩客IP>/
```

**手动 Smoke Test**（浏览器）：
- [ ] `/login` 页面能显示，SSO 按钮可见
- [ ] 用 Keycloak 账号能登录，跳 `/query`
- [ ] `/query` 发送 "What is the max clock of STM32F407?" → 看到**真实** LLM 回答 + citation
- [ ] `/compare` 选两个芯片，点对比 → 看到参数表
- [ ] `/documents` 上传一个小 PDF → 5s 轮询看 status 从 pending → processing → done
- [ ] 登出后再进 `/query` → 应跳 `/login?redirect=/query`

**Playwright E2E 对真后端**：
- MSW handlers 保留作为本地 mock 模式
- 新建 `e2e/tests/*.real.spec.ts` 对真后端跑，或用环境变量切换
- 本轮可推迟（smoke test 通过就够了）

---

## Phase 10 — 负载测试

```bash
# Smoke profile
locust -f tests/load/locustfile.py --host http://localhost:8080 \
  --headless --users 5 --spawn-rate 1 --run-time 1m

# Baseline profile
locust -f tests/load/locustfile.py --host http://localhost:8080 \
  --headless --users 50 --spawn-rate 5 --run-time 10m
```

**SLO 目标**（来自 `config/prometheus/alert_rules.yml`）：
- p95 latency < 10s
- 5xx rate < 5%
- 稳态下 LM Studio 健康

**若 SLO 未达**：
- p95 高：LM Studio 瓶颈（35B 推理慢），看 `max_concurrent` 是否被打满
- 5xx 率高：看 trace log（`logs/traces.jsonl`），通常是 orchestrator tool 调用失败
- OOM：`docker stats` 看内存，Milvus 或 PaddleOCR 是大户

---

## Phase 11 — 接收 Checklist（给业务方看的）

- [ ] `/readiness` 全绿
- [ ] SSO 登录全流程通
- [ ] 查询一个已知芯片（如 STM32F407）能得到**准确**答案 + **可点击**的 citation
- [ ] 上传一份 datasheet → 10 分钟内完成摄入 → 能查询
- [ ] 多轮对话：连续问 3 个相关问题，上下文被正确记住
- [ ] 报告导出：生成一份对比报告 PDF/Excel
- [ ] Grafana 4 个 dashboard 有实时数据
- [ ] 告警规则能触发（手动 stop LM Studio 10s，看 `LMStudioDown` 告警是否 pending/firing）

---

## Phase 12 — 已知风险 & 应急

**高概率会炸的点**：

1. **prompt 模板在 qwen3-35b 上不 work** — 本地全程 mock，没有真 LLM 行为验证。极摩客上 JSON 输出格式、工具调用格式、citation 引用格式都可能需要微调 `config/prompts/*.txt`
2. **Agent 5 轮迭代不够** — 复杂查询可能超出 `max_iterations`，调 `config/settings.yaml:agent.max_iterations` 或改 prompt 让 agent 更简洁
3. **Milvus 索引参数** — HNSW M=16/efC=256 是经验值，大数据量下可能召回率不够，需要调 `efSearch`
4. **JWT 密钥路径** — `/run/secrets/jwt-*.pem` 是 linux 约定，权限问题可改 `config/settings.yaml:auth.jwt.private_key_path` 指向 `./secrets/`
5. **Celery worker 掉线** — heavy 队列的 PaddleOCR 吃内存，易被 OOM kill，看 `dmesg` 和 `docker logs`

**回滚策略**：每个 Phase 都是 `docker compose down <service>` 即可回退。数据层（PG/Milvus）migration 出问题时 `alembic downgrade -1` 再重跑。

**求助**：在极摩客上任何 Phase 卡住，把错误贴给 Claude，Claude 会从本文档已知的上下文出发帮你诊断。
