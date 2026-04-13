# ChipWise Enterprise — 运维手册

**版本**: 1.0 | **更新日期**: 2026-04-13

---

## 日常运维

### 健康检查

```bash
# Quick health check (all services)
python scripts/healthcheck.py

# API health endpoints
curl http://localhost:8080/health      # liveness: {"status": "ok"}
curl http://localhost:8080/readiness   # readiness: lists each service status

# Docker container status
docker compose ps

# Celery worker status
source .venv/bin/activate
celery -A src.ingestion.tasks inspect active
celery -A src.ingestion.tasks inspect reserved
```

### 服务启停

```bash
# Start all services
bash scripts/start_services.sh

# Stop application (keep Docker infra running)
pkill -f "uvicorn src.api.main"
pkill -f "celery.*worker"
pkill -f "frontend/gradio_app"

# Stop all Docker services
docker compose down

# Restart a single container
docker compose restart postgres
docker compose restart redis
```

### 日志查看

```bash
# FastAPI access logs (stdout)
journalctl -u chipwise-api -f

# Distributed traces (one JSON object per line)
tail -f logs/traces.jsonl | python -m json.tool

# Celery task logs
tail -f logs/celery-worker1.log

# Docker service logs
docker compose logs -f milvus
docker compose logs -f postgres --tail=100
```

**traces.jsonl 结构**：
```json
{
  "trace_id": "abc123",
  "request_id": "req-456",
  "user_id": "user_789",
  "stages": [
    {"name": "cache_check", "duration_ms": 2, "hit": false},
    {"name": "query_rewrite", "duration_ms": 180},
    {"name": "vector_search", "duration_ms": 45, "results": 10},
    {"name": "rerank", "duration_ms": 90, "results": 5},
    {"name": "llm_generate", "duration_ms": 3200, "tokens": 512}
  ],
  "total_ms": 3520
}
```

---

## 备份与恢复

### 每日自动备份

添加到 crontab（`crontab -e`）：
```cron
0 3 * * * /home/chipwise/scripts/backup.sh >> /var/log/chipwise-backup.log 2>&1
```

### PostgreSQL

```bash
# Backup
pg_dump -h localhost -U chipwise chipwise | gzip > backups/pg_$(date +%Y%m%d).sql.gz

# Restore
gunzip -c backups/pg_20260413.sql.gz | psql -h localhost -U chipwise chipwise
```

### Milvus

```bash
# Snapshot (Milvus built-in)
curl -X POST "http://localhost:9091/api/v1/snapshot" \
  -H "Content-Type: application/json" \
  -d '{"collection_name": "chipwise_chunks"}'

# Or: stop Milvus and copy the data volume
docker compose stop milvus
tar -czf backups/milvus_$(date +%Y%m%d).tar.gz volumes/milvus/
docker compose start milvus
```

### Kùzu（嵌入式）

```bash
# Kùzu stores data in data/kuzu/ — simple file copy
cp -r data/kuzu/ backups/kuzu_$(date +%Y%m%d)/
```

### Redis

```bash
# Trigger RDB dump
redis-cli -a "$REDIS_PASSWORD" BGSAVE

# Copy the dump file
cp /var/lib/redis/dump.rdb backups/redis_$(date +%Y%m%d).rdb

# Restore: replace dump.rdb and restart
sudo systemctl restart redis
```

---

## 故障诊断手册

### LLM 超时 / 响应缓慢

**现象**：查询响应超过 30 秒或返回 `504 Gateway Timeout`

**诊断**：
```bash
# Check LM Studio is running
curl http://localhost:1234/v1/models

# Check active LLM requests
celery -A src.ingestion.tasks inspect active

# Check token semaphore (should be < 2 for primary, < 10 for router)
redis-cli -a "$REDIS_PASSWORD" LLEN ratelimit:llm:semaphore
```

**解决方案**：
1. 如果 LM Studio 无响应：重启 LM Studio，等待模型加载（约 30 秒）
2. 如果信号量卡死（所有请求完成后仍 >0）：`redis-cli DEL ratelimit:llm:semaphore`
3. 降低并发负载：在 settings.yaml 中调低 `agent.max_concurrent_requests`
4. 如果 Celery heavy 队列积压：扩展 `worker2` → `celery ... worker -c 2`

---

### Milvus 内存溢出 (OOM)

**现象**：Milvus 容器因 OOM 错误退出；向量搜索返回 500

**诊断**：
```bash
docker compose logs milvus --tail=50
docker stats --no-stream milvus-standalone
```

**解决方案**：
1. 在 `docker-compose.yml` 中增加 Docker 内存限制（Milvus 部分：`mem_limit: 12g`）
2. 缩减索引大小：压缩集合或删除不常用的集合
3. 如果 Milvus 数据损坏：从最近的正常快照恢复

**Celery 自动暂停（§3.1 内存保护）**：
- Celery beat 每 60 秒监控系统内存
- 如果可用 RAM < 8 GB，beat 自动暂停 `embedding` 队列
- 在 Prometheus 触发告警：`chipwise_memory_pressure_total > 0`

---

### Celery 任务积压

**现象**：摄入任务已入队但未处理；`/api/v1/tasks/{id}` 一直停留在 `pending` 状态

**诊断**：
```bash
# Check queue depths
celery -A src.ingestion.tasks inspect reserved
redis-cli -a "$REDIS_PASSWORD" LLEN celery

# Check for failed tasks
celery -A src.ingestion.tasks events --dump
```

**解决方案**：
1. 重启卡死的 worker：`celery -A src.ingestion.tasks control shutdown`；然后重启 worker
2. 如果任务中毒（持续失败）：`celery -A src.ingestion.tasks purge`（清空队列）
3. 检查日志中的重复错误；在重新摄入文档之前先修复根本原因

---

### 缓存失效

**现象**：查询结果过期；数据更新后用户仍获取旧的回答

**诊断**：
```bash
# Check cache key count
redis-cli -a "$REDIS_PASSWORD" KEYS "gptcache:*" | wc -l
```

**解决方案**：
```bash
# Flush semantic cache only (keep sessions and rate limits)
redis-cli -a "$REDIS_PASSWORD" KEYS "gptcache:*" | xargs redis-cli -a "$REDIS_PASSWORD" DEL

# Or flush all cache (nuclear option — logs out all users)
redis-cli -a "$REDIS_PASSWORD" FLUSHDB
```

---

### 内存峰值告警 (§3.1)

**Prometheus 告警**：`chipwise_system_memory_available_bytes < 8589934592`（< 8 GB）

**立即处置**：
1. 暂停 Celery `heavy` 队列：`celery -A src.ingestion.tasks control rate_limit heavy 0`
2. 检查哪个进程占用内存：`ps aux --sort=-%mem | head -20`
3. 如果是 Milvus 造成的：增加 swap 或降低 Milvus 配置中的 `queryNode.cache.memoryUsageFactor`
4. 如果是 LM Studio：在 settings.yaml 中缩减上下文窗口（`llm.primary.max_tokens: 4096`）

---

### Schema 校验失败告警

**Prometheus 告警**：`chipwise_schema_validation_failures_total > 10`（每 5 分钟）

**诊断**：
```bash
grep "schema_validation_failed" logs/traces.jsonl | tail -20
```

**解决方案**：
- 高失败率通常意味着 LLM 产生了非 JSON 格式的幻觉输出
- 更新 `config/prompts/` 中的提示模板，使 JSON 格式要求更加明确
- 检查 `llm.primary.temperature` — 数值 > 0.7 会增加幻觉率

---

## Token 用量监控 (§2.11)

ChipWise 通过 Prometheus 追踪 LLM Token 消耗，并提供每日/每周汇总。

### Prometheus 指标

```
chipwise_llm_tokens_total{model="qwen3-35b", role="primary", token_type="prompt"}
chipwise_llm_tokens_total{model="qwen3-35b", role="primary", token_type="completion"}
chipwise_llm_tokens_total{model="qwen3-1.7b", role="router", token_type="prompt"}
```

**Grafana 面板**：`chipwise-overview` 仪表盘中的 "LLM Token Usage" 面板。

### 通过 API 查看每日汇总

```bash
# Today's token usage
curl http://localhost:8080/api/v1/monitoring/token-usage

# Weekly summary
curl http://localhost:8080/api/v1/monitoring/token-usage?period=week
```

### 成本控制阈值

| 告警 | 阈值 | 处置措施 |
|---|---|---|
| 每日 Token 突增 | > 200 万 tokens/天 | 排查查询模式；检查是否存在循环调用 |
| 路由模型过载 | > 500 万路由 tokens/天 | 增加缓存 TTL 以减少重复调用 |
| 主模型压力 | 内存峰值与 Token 峰值关联 | 临时降低 `max_tokens` |

---

## CI/CD 流水线

ChipWise 使用 GitHub Actions 进行持续集成。

### Phase 1 工具链（当前使用）

| 工具 | 用途 | 触发条件 |
|---|---|---|
| `ruff check src tests` | 代码检查 | 每次 PR |
| `mypy src` | 类型检查 | 每次 PR |
| `pytest -q -m unit` | 单元测试（无需 Docker） | 每次 PR |
| GitHub CodeQL (Python) | 静态安全分析 | 每次 PR + 每周 |
| Trivy 文件系统扫描 | CVE + 配置错误 + 密钥泄露检测 | 每次 PR |
| `pip-audit` | 依赖漏洞扫描 | 每周 |

### Phase X 工具链（未来）

- SonarQube：代码质量门禁（重复代码、复杂度、覆盖率）
- Helm：Kubernetes 部署自动化
- 针对预发布集群的集成测试套件

### 本地运行 CI

```bash
source .venv/bin/activate

# Lint + type check
ruff check src tests && mypy src

# Unit tests only (no Docker required)
pytest -q -m unit

# Full test suite (requires Docker services)
docker compose up -d
pytest -q

# Security scan (requires pip-audit installed)
pip-audit
```

---

## 日志轮转

添加到 `/etc/logrotate.d/chipwise`：
```
/home/chipwise/chipwise-enterprise/logs/*.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
}

/home/chipwise/chipwise-enterprise/logs/traces.jsonl {
    daily
    rotate 7
    compress
    missingok
    notifempty
    copytruncate
}
```

---

## 扩展指南

### 垂直扩展（当前：单机部署）

在同一台机器上支持更多并发用户：
1. 增加 Celery worker 并发数：将 `worker1` 的 `-c 1` 改为 `-c 2`
2. 在 docker-compose.yml 中增加 Redis `maxmemory`
3. 增加 PostgreSQL `max_connections` 和 `shared_buffers`

### 水平扩展（Phase X: Kubernetes）

1. 使用 Helm chart 打包（Phase X 实施后参见 `deploy/helm/`）
2. 通过 HPA 扩展无状态 Worker（FastAPI、Celery）
3. 使用 PostgreSQL 集群（Patroni/CloudNativePG）实现高可用
4. 使用 Milvus Cluster 模式（Pulsar + 多查询节点）
5. LM Studio → vLLM 或 Triton Inference Server 实现 GPU 优化多副本推理

```
Phase 1: single machine, Docker Compose
Phase X: Kubernetes, Helm, HPA, multi-replica
```
