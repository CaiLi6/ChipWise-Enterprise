# 5. 测试方案与可观测性

## 5.1 测试策略与覆盖率要求

| 阶段 | 覆盖率要求 | 测试类型 |
|------|-----------|---------|
| 核心逻辑 (`core/`, `pipelines/`) | ≥ 80% | Unit + Integration |
| API 层 (`api/`) | ≥ 70% | Unit + E2E |
| Libs 层 (`libs/`) | ≥ 90% | Unit (Mock 外部依赖) |
| 整体 | ≥ 75% | All |

## 5.2 RAG 质量指标

> 参见 [§2.10 RAG 质量评估](#210-rag-质量评估) 了解完整评估框架与黄金测试集维护流程。

| 指标 | 目标 | 测量方式 |
|------|------|---------|
| Hit Rate@10 | ≥ 90% | Golden test set, 100+ 问答对 |
| NDCG@10 | ≥ 0.85 | Golden test set (§2.10) |
| MRR | ≥ 0.80 | Golden test set |
| EM (Exact Match) | ≥ 0.70 | 参数数值精确匹配 (§2.10) |
| F1 (Token-level) | ≥ 0.85 | 答案 Token 级别 F1 (§2.10) |
| Faithfulness | ≥ 0.90 | Ragas / 人工抽检 |
| 参数提取准确率 | ≥ 95% | 与人工标注对比 |
| Schema 校验通过率 | ≥ 98% | Pydantic 校验 + 领域规则 (§2.9) |
| Agent Tool 选择准确率 | ≥ 90% | 标注测试集 (v3.0) |
| 图谱查询命中率 | ≥ 85% | 替代料/勘误关联测试集 (v3.0) |
| 芯片匹配准确率 (BOM) | ≥ 90% | 真实 BOM 对比 |

## 5.3 TraceContext 全链路追踪

```python
@dataclass
class TraceContext:
    trace_id: str
    trace_type: str
    start_time: float
    stages: list[StageRecord]
    user_id: Optional[int] = None
    session_id: Optional[str] = None
    intent: Optional[str] = None
    cache_hit: Optional[bool] = None
    agent_iterations: Optional[int] = None
    tools_called: Optional[list[str]] = None

    def record_stage(self, stage_name: str, metadata: dict): ...

    def finalize(self) -> dict:
        return {
            "trace_id": self.trace_id, "user_id": self.user_id,
            "intent": self.intent, "cache_hit": self.cache_hit,
            "total_latency_ms": (time.time() - self.start_time) * 1000,
            "stages": [s.to_dict() for s in self.stages],
        }
```

## 5.4 结构化日志格式

所有日志统一 JSON Lines 格式，写入 `logs/traces.jsonl`：

```json
{
  "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "trace_type": "query",
  "user_id": 42,
  "session_id": "sess_abc123",
  "intent": "chip_comparison + errata_check",
  "cache_hit": false,
  "agent_iterations": 2,
  "tools_called": ["chip_compare", "graph_query"],
  "total_latency_ms": 4120,
  "stages": [
    {"name": "jwt_auth", "duration_ms": 2},
    {"name": "cache_intercept", "duration_ms": 15, "metadata": {"hit": false}},
    {"name": "agent_iteration_0", "duration_ms": 1850, "metadata": {"tools_called": ["chip_compare", "graph_query"]}},
    {"name": "agent_iteration_1", "duration_ms": 2100, "metadata": {"tools_called": ["rag_search"]}},
    {"name": "agent_final_answer", "duration_ms": 120},
    {"name": "response_build", "duration_ms": 12}
  ],
  "timestamp": "2026-04-07T10:23:45.123Z"
}
```

## 5.5 监控仪表盘与告警

### 监控面板

| 面板 | 数据源 | 指标 |
|------|--------|------|
| **系统状态** | Health endpoints | 各服务在线状态、CPU/内存使用 |
| **请求概览** | traces.jsonl | QPS、P50/P95/P99 延迟、缓存命中率 |
| **Agent 指标** | traces.jsonl | 平均迭代次数、Tool 调用分布、Token 消耗/请求 |
| **LLM 监控** | traces.jsonl + Redis | 并发数、排队深度、Token 消耗 |
| **Token 用量追踪** | Prometheus (§2.11) | prompt/completion tokens 每模型、每请求类型；日/周/月趋势 |
| **图谱统计** | Kùzu | 节点数/边数、热门查询路径、图谱覆盖率 |
| **Ingestion 状态** | Celery + PG | 任务队列深度、成功率、处理速度 |

### 告警阈值

| 指标 | 警告 | 严重 |
|------|------|------|
| P95 响应延迟 | > 8s | > 15s |
| LLM 排队深度 | > 5 | > 10 |
| GPTCache 命中率 | < 20% | < 10% |
| Celery 任务积压 | > 50 | > 200 |
| 磁盘使用率 | > 70% | > 85% |
| 内存利用率 | > 85% (§3.1) | > 95% |
| Milvus 查询延迟 | > 500ms | > 2s |
| Schema 校验失败率 | > 5% (§2.9) | > 15% |
| 服务健康检查失败 | 连续 2 次 | 连续 5 次 |
| Token 日用量 (§2.11) | > 日预算 80% | > 日预算 100% |

## 5.6 CI/CD 流水线

四阶段流水线图见 [§2.8](#28-云原生-cicd)。

```yaml
# .github/workflows/ci-cd.yaml
name: ChipWise CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  # Stage 1: Lint + Test + Code Scanning
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e ".[dev]"
      - run: ruff check src/ tests/
      - run: mypy src/ --ignore-missing-imports
      - run: pytest tests/unit/ -v --cov=src --cov-report=xml
      # Phase 1: GitHub Code Scanning (免费, 零运维)
      - uses: github/codeql-action/init@v3
        with: { languages: python }
      - uses: github/codeql-action/analyze@v3
      # Phase X 可选: SonarQube (团队 >50 人时引入)
      # - uses: sonarSource/sonarcloud-github-action@v2

  # Stage 2: Docker Build + Trivy
  build-and-scan:
    needs: lint-and-test
    steps:
      - run: docker build -t $IMAGE:$SHA .
      - uses: aquasecurity/trivy-action@master
        with: { severity: "CRITICAL,HIGH", exit-code: 1 }
      - run: docker push $IMAGE:$SHA  # if push event

  # Stage 3: Integration Tests
  integration-tests:
    needs: build-and-scan
    services:
      postgres: { image: "postgres:15", ports: ["5432:5432"] }
      redis: { image: "redis:7-alpine", ports: ["6379:6379"] }
    steps:
      - run: pytest tests/integration/ -v --timeout=120

  # Stage 4: Deploy
  deploy-staging:
    if: github.ref == 'refs/heads/develop'
    needs: integration-tests
    steps:
      # Phase 1 主力: Docker Compose 通过 SSH 处推部署
      - run: ssh chipwise-host "cd /opt/chipwise && docker-compose pull && docker-compose up -d --remove-orphans"
      # 备用: Helm 部署 (Phase X 云原生架构储备)
      # - run: helm upgrade --install chipwise ... -f values-staging.yaml --atomic

  deploy-production:
    if: github.ref == 'refs/heads/main'
    needs: integration-tests
    environment: { name: production, url: "https://chipwise.company.com" }
    steps:
      # Phase 1 主力: Docker Compose 通过 SSH 处推部署
      - run: ssh chipwise-host "cd /opt/chipwise && docker-compose pull && docker-compose up -d --remove-orphans"
      # 备用: Helm 部署 (Phase X 云原生架构储备)
      # - run: helm upgrade --install chipwise ... -f values-prod.yaml --atomic
```

## 5.7 代码质量与安全扫描

**Phase 1 代码质量门 (GitHub Code Scanning + Ruff + mypy)**:

| 指标 | 工具 | 阈值 |
|------|------|------|
| Lint 通过率 | Ruff | 0 errors |
| 类型检查 | mypy | 0 errors (--ignore-missing-imports) |
| Coverage | pytest-cov | ≥ 75% |
| 安全漏洞 | GitHub CodeQL | 0 high/critical alerts |

**Phase X 可选: SonarQube 质量门 (团队 >50 人时引入)**:

| 指标 | 阈值 |
|------|------|
| Coverage | ≥ 75% |
| Duplicated Lines | ≤ 5% |
| Maintainability Rating | A |
| Reliability Rating | A |
| Security Rating | A |

**Trivy 镜像安全策略**:

| 级别 | 处理方式 |
|------|---------|
| **CRITICAL / HIGH** | 阻断流水线, 必须修复 |
| **MEDIUM** | 告警, SARIF 上传 GitHub Security tab |
| **LOW** | 记录日志, 不阻断 |

扫描范围: `vuln` (CVE) + `secret` (硬编码密钥) + `misconfig` (Dockerfile/K8s 配置)

---
