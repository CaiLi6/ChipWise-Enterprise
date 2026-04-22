# ChipWise Enterprise — 安全审计报告

**标准**: OWASP Top 10 (2021)
**日期**: 2026-04-13
**范围**: ChipWise Enterprise v1.0 — FastAPI 网关、Agent 工具、数据摄取流水线、SSO/OIDC 层
**工具**: GitHub CodeQL (Python)、Trivy (CVE + 配置错误 + 密钥泄露)、pip-audit、自动化安全测试

---

## 总览

| OWASP 类别 | ID | 状态 | 证据 |
|---|---|---|---|
| 失效的访问控制 (Broken Access Control) | A01 | 通过 | 所有受保护路由均需 JWT；缺少令牌时返回 401 |
| 加密机制失效 (Cryptographic Failures) | A02 | 通过 | 密码使用 bcrypt 哈希；JWT 使用 RS256 签名 |
| 注入 (Injection) | A03 | 通过 | 全面使用参数化查询；Cypher 仅允许只读操作 |
| 不安全设计 (Insecure Design) | A04 | 通过 | 上传时校验文件类型和大小 |
| 安全配置错误 (Security Misconfiguration) | A05 | 通过 | 生产环境 debug=False；CORS 白名单已启用 |
| 易受攻击和过时的组件 (Vulnerable Components) | A06 | 通过 | pip-audit：依赖中 0 个已知 CVE |
| 身份认证和鉴权失效 (Identification & Auth Failures) | A07 | 通过 | 暴力破解防护（5 次失败 → 锁定 5 分钟） |
| 软件和数据完整性失效 (Software & Data Integrity) | A08 | 通过 | Celery 任务签名；无不安全的反序列化 |
| 安全日志和监控失效 (Security Logging Failures) | A09 | 通过 | 密码和令牌已从所有日志输出中脱敏 |
| 服务端请求伪造 (SSRF) | A10 | 通过 | 爬虫 URL 白名单：st.com、ti.com、nxp.com |

**结果：10/10 项检查全部通过。未发现严重 (Critical) 或高危 (High) 漏洞。**

---

## A01 — 失效的访问控制 (Broken Access Control)

**测试**：未携带 JWT 访问 `/api/v1/query` → HTTP 401
**测试**：使用 `role=user` 令牌访问仅管理员端点 → HTTP 403

**实现方式**：
- `/api/v1/` 下的所有路由（`/health`、`/readiness`、`/api/v1/auth/*` 除外）均要求 `Authorization: Bearer <token>`
- 基于角色的访问控制：`admin` 端点校验 JWT 载荷中的 `role == "admin"`
- JWT 校验位于 `src/api/dependencies.py` — 令牌缺失或无效时抛出 `HTTPException(401)`

**证据**：`tests/security/test_owasp_checklist.py::test_a01_access_control`

---

## A02 — 加密机制失效 (Cryptographic Failures)

**测试**：注册用户密码以 bcrypt 哈希存储（非明文）
**测试**：JWT 使用 RS256（非对称密钥）签名

**实现方式**：
- `src/auth/password.py` 中使用 `passlib[bcrypt]` 进行密码哈希
- JWT 令牌通过 `python-jose` 使用 RS256；私钥存储在 `JWT_SECRET_KEY` 环境变量中（绝不写入代码）
- 生产环境通过反向代理（Nginx）强制 HTTPS
- 敏感环境变量（`PG_PASSWORD`、`REDIS_PASSWORD`、`SSO_CLIENT_SECRET`）绝不写入磁盘或日志

**证据**：`tests/security/test_owasp_checklist.py::test_a02_password_hashing`

---

## A03 — 注入 (Injection)

**测试**：在查询参数中输入 SQL 注入载荷 `' OR 1=1 --` → HTTP 401/400（被参数化查询阻止）
**测试**：Cypher 查询为只读模式（不允许 WRITE/CREATE/DELETE）

**实现方式**：
- 所有数据库访问均通过 asyncpg 参数化查询（`$1, $2` 占位符）
- Kùzu Cypher：所有面向用户的查询均为只读；Agent 仅执行预批准的查询模板
- API 边界通过 Pydantic 模型校验进行输入清理
- 任何模块中均无原始字符串 SQL 拼接

**证据**：`tests/security/test_owasp_checklist.py::test_a03_sql_injection`

---

## A04 — 不安全设计 (Insecure Design)

**测试**：上传非 PDF 文件 → HTTP 400
**测试**：上传文件超过 100MB → HTTP 413

**实现方式**：
- 文件上传端点在处理前校验 `content_type in {"application/pdf"}`
- `MAX_UPLOAD_SIZE = 100 * 1024 * 1024` 在 `src/api/routers/ingest.py` 中强制执行
- 架构遵循最小权限原则：每个组件仅具有所需的最低权限
- Agent 工具为只读模式（工具调用不会直接写入生产数据库）

**证据**：`tests/security/test_owasp_checklist.py::test_a04_file_upload_validation`

---

## A05 — 安全配置错误 (Security Misconfiguration)

**测试**：生产配置中 `settings.debug` 为 False
**测试**：设置 `auth.cors_origins` 后，CORS `allow_origins` 为白名单（非 `*`）

**实现方式**：
- `config/settings.yaml` 中生产环境设置 `debug: false`
- CORS 在 `src/api/main.py` 中通过 `settings.auth.cors_origins` 白名单配置
- Docker 容器以非 root 用户运行（UID 1000）
- 密钥通过环境变量注入，绝不提交至 git 的配置文件中

**证据**：`tests/security/test_owasp_checklist.py::test_a05_security_misconfiguration`

---

## A06 — 易受攻击和过时的组件 (Vulnerable and Outdated Components)

**扫描**：对 `requirements.txt` 执行 `pip-audit`
**扫描**：Trivy 文件系统扫描 Python 包和系统库中的 CVE

**结果**：当前依赖集中 0 个已知 CVE（扫描日期：2026-04-13）

**自动化 CI**：`.github/workflows/security-scan.yaml` 在每个 PR 上运行 GitHub CodeQL + Trivy。结果以 SARIF 格式上传至 GitHub Security 标签页。

**证据**：`.github/workflows/security-scan.yaml`，CI 任务日志

---

## A07 — 身份认证和鉴权失效 (Identification and Authentication Failures)

**测试**：连续 5 次登录失败 → 账户锁定 5 分钟 → 429 Too Many Requests

**实现方式**：
- `src/api/middleware/rate_limit.py` 中的速率限制：Redis 键 `ratelimit:{user_id}:failed_logins`，TTL 300 秒
- 5 分钟内 5 次失败后：后续尝试返回 HTTP 429 并携带 `Retry-After` 头
- 密码具有最低复杂度要求（注册时强制执行）
- 会话令牌在闲置 30 分钟后过期（Redis TTL 1800 秒）

**证据**：`tests/security/test_owasp_checklist.py::test_a07_brute_force_protection`

---

## A08 — 软件和数据完整性失效 (Software and Data Integrity Failures)

**测试**：Celery 任务消息已签名（HMAC）；篡改的消息被拒绝
**测试**：不对不可信数据进行 `pickle` 反序列化

**实现方式**：
- Celery 配置为 `task_serializer='json'` + HMAC 签名密钥（`CELERY_SIGNING_KEY` 环境变量）
- 代码库中未使用 `pickle`（通过 `grep -r "pickle" src/` 验证）
- `requirements.txt` 中锁定依赖版本，CI 中进行哈希校验

**证据**：`tests/security/test_owasp_checklist.py::test_a08_data_integrity`

---

## A09 — 安全日志和监控失效 (Security Logging and Monitoring Failures)

**测试**：使用错误密码登录 → 日志条目中不包含密码值
**测试**：JWT 令牌值不出现在追踪日志中

**实现方式**：
- `src/core/logging.py` 定义了 `SensitiveDataFilter`，对匹配 `password|token|secret|key|credential` 的字段进行脱敏
- `logs/traces.jsonl` 存储 `trace_id`、`stage`、`duration_ms`、`metadata` — 绝不存储原始请求体
- 所有日志处理器在写入前应用过滤器
- Prometheus 指标不暴露个人身份信息 (PII)

**证据**：`tests/security/test_owasp_checklist.py::test_a09_no_sensitive_logging`

---

## A10 — 服务端请求伪造 (Server-Side Request Forgery, SSRF)

**测试**：爬虫使用 URL `http://internal-service:6379/` → 被拒绝（不在白名单中）
**测试**：爬虫使用 URL `https://www.st.com/content/...` → 允许通过

**实现方式**：
- `src/ingestion/crawler.py` 根据 `settings.ingestion.crawler_allowed_domains` 校验 URL
- 默认白名单：`["st.com", "ti.com", "nxp.com", "infineon.com", "microchip.com"]`
- URL 校验拒绝私有 IP 范围（RFC1918：10.x、172.16-31.x、192.168.x）和回环地址
- Playwright 浏览器沙箱已启用；无法访问宿主机文件系统

**证据**：`tests/security/test_owasp_checklist.py::test_a10_ssrf_protection`

---

## 静态分析 (GitHub CodeQL)

配置文件：`.github/workflows/security-scan.yaml`

- **语言**：Python
- **查询集**：`security-and-quality` 查询套件
- **调度**：每个 PR 触发 + 每周在 `main` 分支上运行
- **结果**：SARIF 格式 → GitHub Security 标签页 → Code Scanning Alerts

Phase 1 代码库中未发现可操作的告警。

---

## 依赖扫描 (Trivy)

```bash
trivy fs . --scanners vuln,secret,misconfig --severity CRITICAL,HIGH
```

- **漏洞**：0 CRITICAL，0 HIGH
- **密钥泄露**：未检测到硬编码密钥（所有密钥通过环境变量注入）
- **配置错误**：Docker 镜像使用非 root 用户；无 SUID 二进制文件

---

## 残余风险与缓解措施

| 风险 | 严重程度 | 缓解措施 | 阶段 |
|---|---|---|---|
| LM Studio 在 :1234 上无身份认证运行 | 中 | 防火墙规则：阻止外部网络访问 :1234 | Phase 1 |
| Kùzu 嵌入式数据库：无静态加密 | 低 | 操作系统级磁盘加密 (LUKS)；Kùzu 数据目录置于加密卷上 | Phase X |
| 单机部署：无高可用 | 低 | Phase X：Kubernetes 多节点部署 + PDB | Phase X |
| JWT RS256 密钥轮换 | 中 | 通过 CI 脚本每 90 天自动轮换密钥 | Phase X |

---

*本报告作为 ChipWise Enterprise Phase 6 交付的一部分生成。在任何重大依赖更新或架构变更后应重新审计。*
