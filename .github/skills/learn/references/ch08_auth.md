# Chapter 8: Authentication (认证鉴权)

## Teaching Guide

### 1. Introduction

**Connect to Chapter 2**: "还记得 API Gateway 的 JWT 中间件吗？今天我们深入看看认证系统——SSO 登录、JWT 签发、权限管理。"

### 2. Key Concepts

#### SSO/OIDC Flow

```
User → /login → 302 Redirect to IdP (Keycloak/DingTalk/Feishu)
                                │
User ← IdP login page ←────────┘
                │ (user logs in)
                ▼
IdP → /callback?code=xxx&state=yyy
        │
        ├─ Verify CSRF state (Redis GETDEL)
        ├─ Exchange code for tokens (IdP API)
        ├─ JIT Provision (create/update local user in PG)
        └─ Issue ChipWise JWT → Set cookie → Redirect to app
```

#### 3 SSO Providers (all inherit BaseSSOProvider)

- `KeycloakProvider` — 企业标准 OIDC
- `DingTalkProvider` — 钉钉扫码登录
- `FeishuProvider` — 飞书登录

#### JIT Provisioning

First login → auto-create user in PostgreSQL with role mapping:
```
IdP group "chipwise-admin"     → role: admin
IdP group "chipwise-engineers" → role: user
IdP group "chipwise-viewers"   → role: viewer
default                        → role: viewer
```

Priority: admin > user > viewer (highest group wins)

#### CSRF State Store

```python
# Login: store state
redis.setex(f"sso:state:{state}", 600, json.dumps(metadata))

# Callback: verify & consume (one-time use)
data = redis.getdel(f"sso:state:{state}")  # atomic get + delete
```

### 3. Code Walkthrough

**Files to read**:

1. `src/auth/sso/base.py` — BaseSSOProvider ABC
2. `src/auth/sso/keycloak.py` — Full OIDC implementation
3. `src/auth/sso/state_store.py` — Redis CSRF state
4. `src/auth/sso/jit_provisioner.py` — User auto-creation
5. `src/api/routers/auth.py` — Local JWT fallback

### 5. Quiz Questions

**Q1 (Concept)**: 为什么 CSRF state 存在 Redis 而不是内存 dict？

**A1**: 1) 多 worker/进程场景下内存 dict 不共享; 2) SETEX 自动过期（600s），不需要手动清理; 3) GETDEL 原子性保证一次性使用，防重放攻击; 4) 服务重启不影响进行中的登录流程（Redis 有持久化）。

**Q2 (Code reading)**: JIT provisioner 的 role mapping 是 "priority-based"。如果一个用户同时属于 "chipwise-admin" 和 "chipwise-viewers" 两个组，最终角色是什么？

**A2**: admin。Priority: admin > user > viewer，取最高优先级。代码遍历用户的所有组，映射到角色列表，取优先级最高的那个。

**Q3 (Design)**: 开发环境不想配 Keycloak，怎么登录测试？

**A3**: 使用 `local_fallback` 模式。`auth.local_fallback.enabled: true` 启用本地 JWT 认证（用户名密码存 PG），`auth.local_fallback.jwt_secret` 用对称密钥签名。FastAPI 单元测试更简单：`app.dependency_overrides[get_current_user] = lambda: mock_user`。
