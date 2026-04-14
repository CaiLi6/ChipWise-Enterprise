# 后端开发完全学习指南
## 基于 ChipWise Enterprise 项目 · 面向大厂面试

> **作者说明**：本指南以 ChipWise Enterprise 项目为实战案例，系统讲解后端开发的全部核心知识。
> 每个知识点都配有"是什么 → 为什么 → 怎么用 → 项目里怎么做 → 面试考点"五层结构。
> 预计阅读时长：20-30 小时（建议配合代码实践）。

---

## 目录

1. [后端开发全局观](#第1章-后端开发全局观)
2. [HTTP 协议深度解析](#第2章-http协议深度解析)
3. [REST API 设计规范](#第3章-rest-api设计规范)
4. [Python 后端开发基础](#第4章-python后端开发基础)
5. [FastAPI 框架完全教程](#第5章-fastapi框架完全教程)
6. [关系数据库与 PostgreSQL](#第6章-关系数据库与postgresql)
7. [ORM、迁移与 SQLAlchemy](#第7章-orm迁移与sqlalchemy)
8. [Redis 缓存与会话](#第8章-redis缓存与会话)
9. [向量数据库 Milvus](#第9章-向量数据库milvus)
10. [异步编程与并发](#第10章-异步编程与并发)
11. [认证与授权：JWT / OAuth2 / SSO](#第11章-认证与授权)
12. [Docker 与容器化](#第12章-docker与容器化)
13. [Celery 任务队列](#第13章-celery任务队列)
14. [安全：OWASP Top 10 实战](#第14章-安全owasp-top-10实战)
15. [可观测性：日志、追踪、监控](#第15章-可观测性)
16. [大厂面试题完全解析](#第16章-大厂面试题完全解析)

---

# 第1章 后端开发全局观

## 1.1 什么是后端？

把一个 Web 应用比作餐厅：

| 餐厅 | Web 应用 |
|------|---------|
| 前厅（服务员、菜单） | 前端（HTML/CSS/JS、Gradio、Vue） |
| 厨房（厨师、烹饪） | 后端（FastAPI、业务逻辑） |
| 仓库（食材存储） | 数据库（PostgreSQL、Milvus、Redis） |
| 收银台 | 认证授权（JWT） |
| 传菜员 | API（HTTP 接口） |

**后端的三个核心职责**：
1. **接收请求**：监听网络端口，解析 HTTP 请求
2. **处理业务**：查数据库、调 AI 模型、执行计算
3. **返回响应**：把结果序列化成 JSON 返回

## 1.2 ChipWise 后端架构全貌

```
用户请求
  │
  ▼
[Nginx/前端 :7860]
  │  HTTP
  ▼
[FastAPI Gateway :8080]  ← 本书核心
  │
  ├─── JWT 认证
  ├─── 限流中间件
  ├─── CORS 中间件
  ├─── TraceID 注入
  │
  ├─── /api/v1/query ──→ AgentOrchestrator
  │                           │
  │                    ReAct 推理循环
  │                           │
  │              ┌────────────┼────────────┐
  │              ▼            ▼            ▼
  │         BGE-M3:8001  LM Studio:1234  bce-reranker:8002
  │              │            │            │
  │         Milvus向量搜索  生成回答      结果重排
  │
  ├─── /api/v1/documents ──→ Celery任务队列
  │                               │
  │                    background: PDF解析→向量化→存储
  │
  └─── 数据存储层
            ├── PostgreSQL :5432  （结构化数据）
            ├── Milvus     :19530 （向量数据）
            ├── Redis      :6379  （缓存/会话）
            └── Kùzu       embedded（知识图谱）
```

## 1.3 技术栈一览表

| 类别 | 技术 | 用途 |
|------|------|------|
| Web 框架 | FastAPI | HTTP 服务器、路由、序列化 |
| 数据验证 | Pydantic v2 | 请求/响应模型验证 |
| 关系数据库 | PostgreSQL 15 | 芯片数据、用户、文档 |
| ORM | SQLAlchemy 2.0 | Python 操作数据库 |
| 数据库迁移 | Alembic | 版本化管理表结构变更 |
| 缓存 | Redis 7 | 语义缓存、会话、限流 |
| 向量数据库 | Milvus 2.4 | 语义相似度搜索 |
| 图数据库 | Kùzu | 知识图谱查询 |
| 任务队列 | Celery + Redis | 异步文档处理 |
| 认证 | JWT + OIDC | 身份验证 |
| 容器化 | Docker Compose | 服务编排 |
| LLM 推理 | LM Studio | 本地模型服务 |
| 嵌入模型 | BGE-M3 | 文本向量化 |

---

# 第2章 HTTP 协议深度解析

## 2.1 HTTP 是什么？

**HTTP（HyperText Transfer Protocol）** 是浏览器和服务器之间传输数据的协议，是整个 Web 的基础。

本质上，HTTP 是一问一答的**文本协议**：

```
客户端（浏览器/前端）  →  发送请求（Request）
服务器（后端）        →  返回响应（Response）
```

## 2.2 HTTP 请求的完整结构

一个真实的 HTTP 请求长这样：

```
POST /api/v1/query HTTP/1.1          ← 请求行（方法 + 路径 + 版本）
Host: localhost:8080                  ← 请求头（Headers）
Content-Type: application/json        ← 告诉服务器我发的是JSON
Authorization: Bearer eyJhbGc...      ← JWT令牌
X-Request-ID: uuid-1234               ← 自定义请求ID
Content-Length: 42                    ← 请求体的字节数

{"query": "STM32的工作电压是多少"}     ← 请求体（Body）
```

**请求行** = `方法 路径 版本`

| 方法 | 含义 | 场景 |
|------|------|------|
| `GET` | 获取资源 | 查询芯片信息 |
| `POST` | 创建/提交资源 | 发起查询、上传文档 |
| `PUT` | 全量替换资源 | 更新整个芯片记录 |
| `PATCH` | 部分更新资源 | 只改某个字段 |
| `DELETE` | 删除资源 | 删除文档 |

## 2.3 HTTP 响应的完整结构

```
HTTP/1.1 200 OK                       ← 状态行（版本 + 状态码 + 状态描述）
Content-Type: application/json        ← 响应头
X-Request-ID: uuid-1234               ← 响应头（服务器回传）
Content-Length: 156                   ← 响应体字节数

{                                     ← 响应体
  "answer": "STM32工作电压为1.8V~3.6V",
  "citations": [...],
  "trace_id": "uuid-1234"
}
```

## 2.4 HTTP 状态码（必须背熟）

状态码是三位数字，第一位表示类别：

### 2xx — 成功

| 状态码 | 含义 | 使用场景 |
|--------|------|---------|
| `200 OK` | 请求成功 | GET/POST 成功返回 |
| `201 Created` | 资源已创建 | POST 创建新资源 |
| `202 Accepted` | 已接受，异步处理中 | 上传文档触发Celery任务 |
| `204 No Content` | 成功但无内容 | DELETE 成功 |

### 3xx — 重定向

| 状态码 | 含义 | 使用场景 |
|--------|------|---------|
| `301 Moved Permanently` | 永久重定向 | 域名迁移 |
| `302 Found` | 临时重定向 | SSO 跳转到 IdP 登录页 |
| `304 Not Modified` | 内容未变 | 浏览器缓存生效 |

### 4xx — 客户端错误（用户的锅）

| 状态码 | 含义 | 使用场景 |
|--------|------|---------|
| `400 Bad Request` | 请求格式错误 | JSON 格式不对 |
| `401 Unauthorized` | 未认证 | 没带 JWT Token |
| `403 Forbidden` | 无权限 | Token 有效但无此权限 |
| `404 Not Found` | 资源不存在 | 查询的芯片不存在 |
| `405 Method Not Allowed` | 方法不允许 | 对只允许POST的接口用GET |
| `409 Conflict` | 冲突 | 用户名已存在 |
| `422 Unprocessable Entity` | 验证失败 | Pydantic 字段校验不通过 |
| `429 Too Many Requests` | 请求过多 | 触发限速 |

### 5xx — 服务端错误（服务器的锅）

| 状态码 | 含义 | 使用场景 |
|--------|------|---------|
| `500 Internal Server Error` | 服务器内部错误 | 代码异常 |
| `502 Bad Gateway` | 上游服务错误 | Nginx 无法连接到 FastAPI |
| `503 Service Unavailable` | 服务不可用 | LM Studio 未启动时返回此状态 |
| `504 Gateway Timeout` | 上游超时 | AI 推理超时 |

> **项目案例**：当 LM Studio 未启动时，`AgentOrchestrator` 返回 `None`，FastAPI 返回 **503**，而不是 500——这就是"优雅降级"。

## 2.5 HTTP Headers 详解

Headers 是键值对形式的元数据，分为请求头和响应头：

### 常见请求头

```
Content-Type: application/json          # 请求体是JSON
Content-Type: multipart/form-data       # 上传文件时用
Authorization: Bearer <token>           # JWT认证
Accept: application/json                # 告诉服务器我想要JSON
Accept-Language: zh-CN                  # 告诉服务器我想要中文
X-Request-ID: uuid                      # 自定义追踪ID
```

### 常见响应头

```
Content-Type: application/json          # 响应体是JSON
Content-Type: text/event-stream         # SSE流式响应
Cache-Control: no-cache                 # 不要缓存
Set-Cookie: session=xxx; HttpOnly       # 设置Cookie
Access-Control-Allow-Origin: *          # CORS允许的域名
```

## 2.6 HTTP/1.1 vs HTTP/2 vs HTTP/3

| 版本 | 关键特性 | 性能 |
|------|---------|------|
| HTTP/1.1 | Keep-Alive 长连接 | 一个连接同时只能处理一个请求 |
| HTTP/2 | 多路复用（一个连接并发多个请求）、头部压缩 | 比1.1快2-4倍 |
| HTTP/3 | 基于 QUIC（UDP），解决队头阻塞 | 弱网环境更优 |

## 2.7 HTTPS 与 TLS

HTTPS = HTTP + TLS 加密。TLS 握手过程：

```
客户端                              服务器
  │                                  │
  │──── ClientHello（支持的加密套件）────▶│
  │                                  │
  │◀─── ServerHello + 证书 ──────────│
  │                                  │
  │── 验证证书（CA签名是否可信）         │
  │                                  │
  │──── 用服务器公钥加密的预主密钥 ──────▶│
  │                                  │
  │◀────── Finished（加密通信开始）────│
  │                                  │
  │════════ 对称加密通信 ════════════════│
```

关键点：
- **非对称加密**（RSA/ECDHE）用于握手阶段，交换密钥
- **对称加密**（AES）用于数据传输，性能高
- **数字证书**由 CA（证书颁发机构）签名，防止篡改

## 2.8 SSE（Server-Sent Events）流式响应

ChipWise 的查询接口支持 SSE 流式返回，实现"打字机效果"：

```
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache

data: STM32的工作

data: 电压范围

data: 是1.8V～3.6V

data: [DONE]
```

前端 JavaScript 用 `EventSource` 接收：
```javascript
const es = new EventSource('/api/v1/query/stream?q=STM32工作电压');
es.onmessage = (e) => append(e.data);
```

Python FastAPI 实现：
```python
from fastapi.responses import StreamingResponse

async def stream_generator():
    async for chunk in llm.stream("STM32工作电压"):
        yield f"data: {chunk}\n\n"

return StreamingResponse(stream_generator(), media_type="text/event-stream")
```

---

# 第3章 REST API 设计规范

## 3.1 什么是 REST？

**REST（Representational State Transfer）** 是一种 API 设计风格，不是协议，是约定。

核心思想：**把一切都抽象成"资源"，用 HTTP 方法操作资源**。

## 3.2 REST 的六大约束

| 约束 | 含义 |
|------|------|
| 无状态（Stateless） | 每个请求包含所有必要信息，服务器不存储会话（JWT就是为此设计） |
| 统一接口 | 用标准方法（GET/POST等）操作资源 |
| 客户端-服务器分离 | 前后端互相独立 |
| 可缓存 | 响应标注是否可缓存 |
| 分层系统 | 客户端不知道是直接连服务器还是通过代理 |
| 按需代码（可选） | 服务器可传输可执行代码给客户端 |

## 3.3 RESTful URL 设计规范

### 核心原则：URL 描述资源，动词用方法表示

```bash
# ✅ 正确 RESTful 风格
GET    /api/v1/chips              # 获取芯片列表
GET    /api/v1/chips/STM32F4      # 获取某个芯片
POST   /api/v1/chips              # 创建芯片
PUT    /api/v1/chips/STM32F4      # 全量更新
PATCH  /api/v1/chips/STM32F4      # 部分更新
DELETE /api/v1/chips/STM32F4      # 删除

# ✅ 嵌套资源
GET    /api/v1/chips/STM32F4/parameters    # 某芯片的参数列表
GET    /api/v1/chips/STM32F4/errata        # 某芯片的勘误

# ❌ 反例（把动词放URL里）
POST   /api/v1/getChip
POST   /api/v1/createChip
POST   /api/v1/deleteChip?id=123
```

### URL 命名规范

```bash
# ✅ 用复数名词
/api/v1/documents
/api/v1/tasks

# ✅ 用连字符分隔单词
/api/v1/chip-parameters
/api/v1/design-rules

# ❌ 不用下划线
/api/v1/chip_parameters

# ❌ 不用驼峰
/api/v1/chipParameters

# ✅ 版本号放在URL或Header
/api/v1/query
# 或 Header: Api-Version: 1
```

## 3.4 查询参数（Query Parameters）

用于过滤、分页、排序，不是资源的一部分：

```bash
# 分页
GET /api/v1/chips?page=2&page_size=20

# 过滤
GET /api/v1/chips?manufacturer=ST&voltage_min=1.8

# 排序
GET /api/v1/chips?sort=name&order=asc

# 搜索
GET /api/v1/chips?q=STM32
```

## 3.5 标准响应格式设计

ChipWise 采用的统一响应格式：

```json
// 成功响应
{
  "data": { ... },           // 业务数据
  "trace_id": "uuid-1234"    // 追踪ID
}

// 错误响应
{
  "error": "ValidationError",
  "detail": "query field is required",
  "trace_id": "uuid-1234"
}

// 分页列表响应
{
  "data": [ ... ],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "trace_id": "uuid-1234"
}
```

## 3.6 幂等性（面试高频）

**幂等** = 执行一次和执行多次，效果相同。

| 方法 | 是否幂等 | 原因 |
|------|---------|------|
| GET | ✅ | 只读，不改变状态 |
| PUT | ✅ | 全量替换，多次结果一样 |
| DELETE | ✅ | 删了就是没了，再删无效果 |
| POST | ❌ | 每次创建新资源 |
| PATCH | ❌通常 | 依赖实现（+1操作不幂等，set操作幂等） |

> **为什么重要**？网络超时重试时，客户端不知道上次请求是否成功，只有幂等操作才能安全重试。

## 3.7 API 版本管理

```bash
# 方式1：URL路径（最常见，ChipWise采用此方式）
/api/v1/query
/api/v2/query   ← 不兼容更新时升版本

# 方式2：请求头
Accept: application/vnd.chipwise.v2+json

# 方式3：查询参数
/api/query?version=2
```

---

# 第4章 Python 后端开发基础

## 4.1 类型注解（Type Hints）

Python 3.5+ 支持类型注解，FastAPI 和 Pydantic 强依赖此特性：

```python
# 基础类型
name: str = "hello"
age: int = 25
price: float = 3.14
active: bool = True

# 容器类型
from typing import List, Dict, Optional, Union, Tuple

names: List[str] = ["STM32", "ESP32"]
params: Dict[str, float] = {"voltage": 3.3}
maybe: Optional[str] = None          # 可能是str，也可能是None
either: Union[str, int] = "hello"    # str或int

# Python 3.10+ 简化写法
names: list[str] = []
params: dict[str, float] = {}
maybe: str | None = None             # 等价于 Optional[str]
```

## 4.2 Pydantic —— 数据验证利器

Pydantic 是 FastAPI 的核心依赖，负责：
- 请求数据验证
- 响应数据序列化
- 配置管理

```python
from pydantic import BaseModel, Field, validator
from typing import Optional

# 定义数据模型
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="用户查询")
    session_id: Optional[str] = Field(None, description="会话ID")
    top_k: int = Field(5, ge=1, le=20, description="返回结果数量")

# 使用
req = QueryRequest(query="STM32的电压", top_k=3)
print(req.query)        # STM32的电压
print(req.model_dump()) # {'query': 'STM32的电压', 'session_id': None, 'top_k': 3}

# 验证失败会抛出 ValidationError
try:
    bad = QueryRequest(query="")   # min_length=1，空字符串不合法
except Exception as e:
    print(e)  # validation error
```

### Pydantic validators 自定义校验

```python
from pydantic import BaseModel, field_validator

class ChipCompareRequest(BaseModel):
    chip_names: list[str]
    
    @field_validator("chip_names")
    @classmethod
    def at_least_two_chips(cls, v):
        if len(v) < 2:
            raise ValueError("至少需要两个芯片型号进行对比")
        return v
```

## 4.3 装饰器（Decorator）

FastAPI 大量使用装饰器，必须理解：

```python
# 装饰器本质：把函数包一层
def log_decorator(func):
    def wrapper(*args, **kwargs):
        print(f"调用 {func.__name__}")
        result = func(*args, **kwargs)
        print(f"{func.__name__} 完成")
        return result
    return wrapper

@log_decorator              # 等价于: greet = log_decorator(greet)
def greet(name):
    return f"Hello, {name}"

# FastAPI中的路由装饰器
@app.get("/chips/{chip_id}")   # 把 get_chip 函数注册为GET /chips/:id 的处理器
async def get_chip(chip_id: str):
    return {"id": chip_id}
```

## 4.4 异步编程基础（async/await）

Python 的异步是**单线程协程**模型，不是多线程：

```python
import asyncio

# 普通函数：同步，会阻塞
def slow_query():
    import time
    time.sleep(2)  # 阻塞！其他请求必须等
    return "result"

# 异步函数：遇到 await 可以切换到其他任务
async def fast_query():
    await asyncio.sleep(2)  # 不阻塞，切换去做别的
    return "result"

# 协程调用
async def main():
    # 串行：总共4秒
    r1 = await fast_query()
    r2 = await fast_query()
    
    # 并行：总共2秒
    r1, r2 = await asyncio.gather(
        fast_query(),
        fast_query()
    )
```

### 什么时候用 async？

```
IO 密集型操作（网络请求、数据库查询、文件读写）→ 用 async，性能提升显著
CPU 密集型操作（数学计算、图像处理）→ 用多进程/多线程，async 无帮助
```

## 4.5 上下文管理器（with 语句）

数据库连接、文件操作必用：

```python
# 文件操作
with open("data.txt", "r") as f:
    content = f.read()
# 出了with块，文件自动关闭——即使发生异常

# 数据库 Session（SQLAlchemy）
with Session() as session:
    chip = session.get(Chip, chip_id)
    session.commit()
# 自动关闭连接，释放连接池资源

# 自定义上下文管理器
from contextlib import asynccontextmanager

@asynccontextmanager
async def managed_connection():
    conn = await create_connection()
    try:
        yield conn
    finally:
        await conn.close()

async def use_it():
    async with managed_connection() as conn:
        await conn.execute("SELECT 1")
```

## 4.6 异常处理

```python
# 基础异常处理
try:
    result = 1 / 0
except ZeroDivisionError as e:
    print(f"除零错误: {e}")
except Exception as e:
    print(f"未知错误: {e}")
    raise  # 重新抛出
finally:
    print("无论如何都会执行")

# 自定义异常
class ChipNotFoundError(Exception):
    def __init__(self, chip_id: str):
        super().__init__(f"芯片 {chip_id} 不存在")
        self.chip_id = chip_id

# 在FastAPI中的全局异常处理（ChipWise项目案例）
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "InternalServerError", "detail": str(exc)}
    )
```

## 4.7 依赖注入（Dependency Injection）

**依赖注入** = 不在函数内部创建依赖，而是从外部"注入"。

好处：解耦、可测试（测试时可以替换成 mock）。

```python
# 不用依赖注入（难测试）
async def get_chip(chip_id: str):
    db = Database()   # 在函数里直接创建，难以替换
    return db.get(chip_id)

# 使用依赖注入（FastAPI方式）
from fastapi import Depends

async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_chip(
    chip_id: str,
    db: Session = Depends(get_db)  # FastAPI会自动注入db
):
    return db.get(Chip, chip_id)

# 测试时替换依赖——ChipWise项目测试模式
app.dependency_overrides[get_current_user] = lambda: fake_user
app.dependency_overrides[get_db] = lambda: fake_db
```

---

# 第5章 FastAPI 框架完全教程

## 5.1 为什么选 FastAPI？

| 框架 | 性能 | 开发速度 | 类型支持 | 异步支持 |
|------|------|---------|---------|---------|
| Django | 中等 | 快（全功能） | 部分 | 有限 |
| Flask | 中等 | 快（轻量） | 无 | 需扩展 |
| **FastAPI** | **最快** | **最快** | **完整** | **原生** |
| Tornado | 快 | 慢 | 无 | 原生 |

FastAPI 基于 **Starlette**（ASGI 框架）和 **Pydantic**（数据验证）构建。

**ASGI vs WSGI**：
- WSGI（Flask/Django）：同步，每个请求占一个线程
- ASGI（FastAPI/Starlette）：异步，一个线程处理多个并发请求

## 5.2 FastAPI 基础路由

```python
from fastapi import FastAPI, Path, Query, Body
from pydantic import BaseModel

app = FastAPI()

# GET 请求 + 路径参数
@app.get("/chips/{chip_id}")
async def get_chip(
    chip_id: str = Path(..., description="芯片型号", regex="^[A-Z0-9]+$")
):
    return {"chip_id": chip_id}

# GET 请求 + 查询参数
@app.get("/chips")
async def list_chips(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, description="搜索关键词")
):
    return {"page": page, "page_size": page_size, "q": q}

# POST 请求 + 请求体
class QueryRequest(BaseModel):
    query: str
    top_k: int = 5

@app.post("/query")
async def query(request: QueryRequest):
    return {"received": request.query, "top_k": request.top_k}
```

## 5.3 路由器（Router）组织代码

当 API 变多时，不能全放在 main.py。用 `APIRouter` 模块化：

```python
# src/api/routers/chips.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/chips", tags=["Chips"])

@router.get("/")
async def list_chips():
    return []

@router.get("/{chip_id}")
async def get_chip(chip_id: str):
    return {"id": chip_id}

# src/api/main.py — 注册路由
from src.api.routers.chips import router as chips_router

app = FastAPI()
app.include_router(chips_router)
# 现在 GET /api/v1/chips/ 和 GET /api/v1/chips/{id} 都注册好了
```

ChipWise 项目就是这样组织的：

```
src/api/routers/
    health.py      → /health, /readiness, /liveness
    auth.py        → /api/v1/auth/login, /api/v1/auth/refresh
    query.py       → /api/v1/query
    compare.py     → /api/v1/compare
    documents.py   → /api/v1/documents/upload
    tasks.py       → /api/v1/tasks/{task_id}
    knowledge.py   → /api/v1/knowledge
    sso.py         → /api/v1/auth/sso/login, /api/v1/auth/sso/callback
```

## 5.4 中间件（Middleware）

中间件是**在请求处理前后执行的代码**，所有请求都会经过：

```
请求 → [中间件1] → [中间件2] → [路由处理函数] → [中间件2] → [中间件1] → 响应
                  （洋葱模型）
```

```python
import time
from fastapi import Request

# 方式1：装饰器中间件
@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.time()
    response = await call_next(request)  # 调用下一层
    duration = time.time() - start
    response.headers["X-Process-Time"] = str(duration)
    return response

# 方式2：类中间件
from starlette.middleware.base import BaseHTTPMiddleware

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 检查限速
        user_id = get_user_id(request)
        if await is_rate_limited(user_id):
            return JSONResponse({"error": "Too Many Requests"}, status_code=429)
        return await call_next(request)

app.add_middleware(RateLimitMiddleware)
```

### ChipWise 的 TraceID 中间件

```python
# src/api/main.py 中的中间件
@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    # 从请求头获取，没有就生成新的
    trace_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.trace_id = trace_id          # 存到request上供后续使用
    response = await call_next(request)
    response.headers["X-Request-ID"] = trace_id  # 响应时也带上
    return response
```

## 5.5 CORS（跨域资源共享）

**什么是跨域**？浏览器的同源策略：协议+域名+端口三者相同才算同源。

```
前端：http://localhost:7860
后端：http://localhost:8080
→ 端口不同 = 跨域 = 浏览器默认拒绝
```

**CORS 解决方案**：服务器在响应头里告诉浏览器"我允许这个来源访问"。

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:7860",    # Gradio 前端
        "http://127.0.0.1:7860",
    ],
    allow_credentials=True,        # 允许携带 Cookie
    allow_methods=["*"],           # 允许所有 HTTP 方法
    allow_headers=["*"],           # 允许所有请求头
)
```

**CORS 预检请求（Preflight）**：
浏览器在发送实际请求前，先用 OPTIONS 方法问服务器"我能发吗？"：
```
OPTIONS /api/v1/query HTTP/1.1
Origin: http://localhost:7860
Access-Control-Request-Method: POST
```
服务器回答：
```
Access-Control-Allow-Origin: http://localhost:7860
Access-Control-Allow-Methods: POST
```
然后浏览器才发真正的 POST。

## 5.6 依赖注入深度讲解

FastAPI 的 `Depends` 系统非常强大：

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

bearer = HTTPBearer()

# 认证依赖：提取并验证JWT
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer)
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        user = await get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token已过期")

# 在路由里使用依赖
@router.post("/query")
async def query(
    request: QueryRequest,
    current_user: User = Depends(get_current_user)  # 自动认证
):
    # 只有认证成功才会到达这里
    return await process_query(request.query, current_user.id)

# 依赖链：依赖也可以依赖别的依赖
async def get_admin_user(
    current_user: User = Depends(get_current_user)  # 依赖get_current_user
) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user
```

### 依赖注入的生命周期

```python
# 请求级别 scope（每个请求都创建新实例）
async def get_db():
    db = SessionLocal()
    try:
        yield db          # yield 之前 = 创建，yield 之后 = 销毁
    finally:
        db.close()

# 使用 yield 的依赖，FastAPI 保证 finally 一定执行（即使路由抛出异常）
```

## 5.7 生命周期事件（Lifespan）

应用启动/关闭时执行初始化或清理：

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    print("初始化数据库连接池...")
    await init_db()
    print("连接 Redis...")
    await init_redis()
    
    yield  # 应用运行中
    
    # 关闭时
    print("关闭数据库连接...")
    await close_db()

app = FastAPI(lifespan=lifespan)
```

## 5.8 请求/响应模型（Schema）

ChipWise 的 schema 设计在 `src/api/schemas/`：

```python
# 请求模型（从客户端收的数据）
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None
    stream: bool = False

# 响应模型（返回给客户端的数据）
class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    trace_id: str
    duration_ms: float

# 在路由中声明，FastAPI 自动生成文档
@router.post(
    "/query",
    response_model=QueryResponse,    # 声明响应模型
    status_code=200,
)
async def query(request: QueryRequest) -> QueryResponse:
    ...
```

## 5.9 自动 API 文档

FastAPI 自动生成 **交互式 API 文档**，无需手写：

- **Swagger UI**：访问 `http://localhost:8080/docs`
- **ReDoc**：访问  `http://localhost:8080/redoc`
- **OpenAPI JSON**：访问 `http://localhost:8080/openapi.json`

这些文档是根据你的路由、Pydantic 模型、类型注解自动生成的。

## 5.10 WebSocket 支持

ChipWise 的任务进度推送用到了 WebSocket：

```python
from fastapi import WebSocket

@router.websocket("/ws/tasks/{task_id}")
async def task_progress_ws(websocket: WebSocket, task_id: str):
    await websocket.accept()
    try:
        while True:
            progress = await get_task_progress(task_id)
            await websocket.send_json(progress)
            if progress["status"] in ("success", "failed"):
                break
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
```

WebSocket vs SSE vs 轮询对比：

| 方案 | 方向 | 连接 | 适用场景 |
|------|------|------|---------|
| 轮询（Polling） | 单向 | 反复建立 | 简单，兼容性好 |
| SSE | 服务器→客户端 | 持久HTTP | LLM流式输出 |
| WebSocket | 双向 | 持久TCP | 实时聊天、任务进度 |

---

# 第6章 关系数据库与 PostgreSQL

## 6.1 关系数据库核心概念

**关系数据库** 把数据组织成**表**（Table），表之间通过**外键**（Foreign Key）关联。

```
chips 表                    parameters 表
┌──────────────────────┐    ┌─────────────────────────────────┐
│ id │ name    │ mfr   │    │ id │ chip_id │ name    │ value  │
├────┼─────────┼───────┤    ├────┼─────────┼─────────┼────────┤
│  1 │ STM32F4 │ ST    │◄───│  1 │       1 │ voltage │ 3.3V   │
│  2 │ ESP32   │ 乐鑫  │    │  2 │       1 │ flash   │ 1MB    │
└──────────────────────┘    │  3 │       2 │ voltage │ 3.3V   │
                            └─────────────────────────────────┘
```

chip_id 是外键，指向 chips.id——这就是"关系"的含义。

## 6.2 SQL 基础（必须掌握）

### DDL — 数据定义语言

```sql
-- 建表
CREATE TABLE chips (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    manufacturer VARCHAR(100),
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 建索引（提高查询速度）
CREATE INDEX idx_chips_name ON chips(name);
CREATE INDEX idx_chips_mfr ON chips(manufacturer);

-- 删表（慎用！）
DROP TABLE chips;

-- 修改表结构
ALTER TABLE chips ADD COLUMN category VARCHAR(50);
ALTER TABLE chips DROP COLUMN category;
```

### DML — 数据操作语言

```sql
-- 插入
INSERT INTO chips (name, manufacturer) VALUES ('STM32F4', 'ST');

-- 查询
SELECT id, name, manufacturer FROM chips WHERE manufacturer = 'ST';

-- 更新
UPDATE chips SET manufacturer = 'STMicroelectronics' WHERE name = 'STM32F4';

-- 删除（真删，慎用！）
DELETE FROM chips WHERE id = 1;

-- 软删除（推荐：加deleted_at字段）
UPDATE chips SET deleted_at = NOW() WHERE id = 1;
```

### 多表查询（JOIN）—— 面试必考

```sql
-- INNER JOIN：两边都有才返回
SELECT c.name, p.name as param_name, p.value
FROM chips c
INNER JOIN parameters p ON c.id = p.chip_id
WHERE c.manufacturer = 'ST';

-- LEFT JOIN：左表全返回，右表没有则NULL
SELECT c.name, COUNT(p.id) as param_count
FROM chips c
LEFT JOIN parameters p ON c.id = p.chip_id
GROUP BY c.id, c.name;

-- 多表JOIN
SELECT c.name, p.name, e.description
FROM chips c
LEFT JOIN parameters p ON c.id = p.chip_id
LEFT JOIN errata e ON c.id = e.chip_id
WHERE c.id = 1;
```

### 聚合查询

```sql
-- 统计每个厂商的芯片数量
SELECT manufacturer, COUNT(*) as chip_count
FROM chips
GROUP BY manufacturer
HAVING COUNT(*) > 5     -- HAVING 是对聚合结果的过滤（不是 WHERE）
ORDER BY chip_count DESC;

-- 常用聚合函数
COUNT(*)      -- 行数
SUM(value)    -- 求和
AVG(value)    -- 平均
MAX(value)    -- 最大
MIN(value)    -- 最小
```

### 子查询

```sql
-- 查询参数最多的前5个芯片
SELECT * FROM chips
WHERE id IN (
    SELECT chip_id
    FROM parameters
    GROUP BY chip_id
    ORDER BY COUNT(*) DESC
    LIMIT 5
);
```

### 重要 SQL 概念

**事务（Transaction）**：

```sql
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
-- 两个操作如果有一个失败，ROLLBACK 回滚全部
COMMIT;
-- 或 ROLLBACK; （出错时回滚）
```

事务的 **ACID** 特性（面试必背）：
- **A**tomicity（原子性）：要么全成功，要么全失败
- **C**onsistency（一致性）：事务前后数据库保持一致状态
- **I**solation（隔离性）：并发事务互不干扰
- **D**urability（持久性）：提交后数据永久保存

## 6.3 索引原理与优化（面试高频）

### B-Tree 索引（默认）

```
           [STM32]
          /        \
    [ESP32]        [TMS320]
    /    \         /     \
[A4]   [M4]   [STM32F4] [Z7]
```

查找 STM32F4 只需要 O(log n) 次比较，而不是全表扫描 O(n)。

```sql
-- 什么时候建索引？
-- 1. 经常用于 WHERE 条件的列
CREATE INDEX idx_chips_name ON chips(name);

-- 2. 经常用于 JOIN 的外键列
CREATE INDEX idx_params_chip_id ON parameters(chip_id);

-- 3. 经常用于 ORDER BY 的列
CREATE INDEX idx_chips_created ON chips(created_at);

-- 联合索引（最左前缀原则！）
CREATE INDEX idx_chips_mfr_name ON chips(manufacturer, name);
-- 这个索引能用于：WHERE manufacturer = 'ST'
-- 也能用于：WHERE manufacturer = 'ST' AND name = 'STM32F4'
-- 但不能用于：WHERE name = 'STM32F4'（没用到最左列manufacturer）
```

### EXPLAIN 分析查询

```sql
EXPLAIN ANALYZE SELECT * FROM chips WHERE name = 'STM32F4';

-- 输出示例：
-- Index Scan using idx_chips_name on chips  (cost=0.29..8.30 rows=1)
--   Index Cond: ((name)::text = 'STM32F4'
--   Actual time=0.048..0.049 rows=1 loops=1

-- 关注：Seq Scan（全表扫描）→ 需要加索引
-- Index Scan（索引扫描）→ 已经用了索引
```

## 6.4 PostgreSQL 特有功能

```sql
-- JSONB — 存储JSON数据并可以查询
ALTER TABLE chips ADD COLUMN metadata JSONB;
UPDATE chips SET metadata = '{"cache": "1MB", "flash": "512KB"}' WHERE id = 1;

-- 查询JSONB字段
SELECT * FROM chips WHERE metadata->>'cache' = '1MB';
SELECT * FROM chips WHERE metadata @> '{"cache": "1MB"}';

-- 全文搜索
SELECT * FROM chips
WHERE to_tsvector('english', description) @@ to_tsquery('voltage & STM32');

-- 窗口函数（高级查询）
SELECT 
    name,
    manufacturer,
    COUNT(*) OVER (PARTITION BY manufacturer) as same_mfr_count
FROM chips;
```

## 6.5 连接池（Connection Pool）

数据库连接很昂贵（建立TCP连接、认证、分配资源），每次请求新建连接会很慢。

**连接池** = 预先建立若干连接，请求来了直接复用：

```
请求1 ──→ 从池中取连接 → 执行SQL → 归还连接到池
请求2 ──→ 从池中取连接 → 执行SQL → 归还连接到池
        ↑
        连接池（保持10个长连接）
        [conn1][conn2][conn3]...[conn10]
```

```python
# SQLAlchemy 连接池配置
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,          # 池中保持的连接数
    max_overflow=20,       # 超出pool_size时最多额外建多少连接
    pool_timeout=30,       # 等待连接的超时时间（秒）
    pool_recycle=3600,     # 连接超过1小时就重建（防止MySQL断开）
)
```

---

# 第7章 ORM、迁移与 SQLAlchemy

## 7.1 什么是 ORM？

**ORM（Object-Relational Mapping）** = 让你用 Python 对象操作数据库，而不用写 SQL。

```python
# 不用ORM（直接SQL）
cursor.execute("SELECT * FROM chips WHERE name = %s", ("STM32F4",))
row = cursor.fetchone()
chip = {"id": row[0], "name": row[1]}  # 手动映射

# 用ORM（SQLAlchemy）
chip = session.get(Chip, "STM32F4")  # 直接得到Python对象
```

ORM 的优缺点：
- ✅ 代码更清晰，不用拼接 SQL 字符串
- ✅ 防止 SQL 注入（参数化查询）
- ✅ 数据库切换容易（换 MySQL 只改配置）
- ❌ 复杂查询性能可能不如手写 SQL
- ❌ 需要学习 ORM 查询语法

## 7.2 SQLAlchemy 2.0 模型定义

```python
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Chip(Base):
    __tablename__ = "chips"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # 关系：一个芯片有多个参数
    parameters: Mapped[list["Parameter"]] = relationship(
        back_populates="chip",
        cascade="all, delete-orphan"
    )

class Parameter(Base):
    __tablename__ = "parameters"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chip_id: Mapped[int] = mapped_column(ForeignKey("chips.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100))
    value: Mapped[str | None] = mapped_column(Text)
    
    # 反向关系
    chip: Mapped["Chip"] = relationship(back_populates="parameters")
```

## 7.3 SQLAlchemy 查询操作

```python
from sqlalchemy import select, update, delete, and_, or_

# 异步Session
from sqlalchemy.ext.asyncio import AsyncSession

async def crud_examples(session: AsyncSession):
    # === 创建 ===
    new_chip = Chip(name="STM32F4", manufacturer="ST")
    session.add(new_chip)
    await session.commit()
    await session.refresh(new_chip)  # 刷新获取数据库生成的ID

    # === 查询 ===
    # 按主键
    chip = await session.get(Chip, 1)
    
    # 条件查询
    stmt = select(Chip).where(Chip.manufacturer == "ST")
    result = await session.execute(stmt)
    chips = result.scalars().all()
    
    # 多条件
    stmt = select(Chip).where(
        and_(
            Chip.manufacturer == "ST",
            Chip.name.like("STM32%")
        )
    )
    
    # JOIN查询
    stmt = (
        select(Chip, Parameter)
        .join(Parameter, Chip.id == Parameter.chip_id)
        .where(Chip.manufacturer == "ST")
    )
    
    # 排序 + 分页
    stmt = (
        select(Chip)
        .order_by(Chip.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    
    # === 更新 ===
    stmt = (
        update(Chip)
        .where(Chip.id == 1)
        .values(manufacturer="STMicroelectronics")
    )
    await session.execute(stmt)
    await session.commit()
    
    # === 删除 ===
    stmt = delete(Chip).where(Chip.id == 1)
    await session.execute(stmt)
    await session.commit()
```

## 7.4 Alembic 数据库迁移

**为什么需要迁移工具**？

随着项目迭代，数据库结构需要变更（加字段、加表、改类型）。
直接修改数据库会导致生产环境数据丢失，且团队协作混乱。

Alembic 像 Git 一样管理数据库变更历史：

```
版本0（空数据库）
    ↓
版本001：创建 chips、parameters 表
    ↓
版本002：给 chips 加 category 字段
    ↓
版本003：创建 errata 表
    ↓
当前版本
```

### Alembic 核心命令

```bash
# 初始化（ChipWise 已完成）
alembic init alembic

# 生成迁移文件（自动检测模型变化）
alembic revision --autogenerate -m "add_category_to_chips"

# 执行迁移（升级到最新）
alembic upgrade head

# 升级到指定版本
alembic upgrade 001_initial_schema

# 回滚一个版本
alembic downgrade -1

# 回滚到最初
alembic downgrade base

# 查看当前版本
alembic current

# 查看变更历史
alembic history
```

### 迁移文件示例

```python
# alembic/versions/001_initial_schema.py
def upgrade() -> None:
    op.create_table(
        "chips",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("manufacturer", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("idx_chips_name", "chips", ["name"])

def downgrade() -> None:
    op.drop_index("idx_chips_name", table_name="chips")
    op.drop_table("chips")
```

---

# 第8章 Redis 缓存与会话

## 8.1 Redis 是什么？

Redis（Remote Dictionary Server）是一个**内存数据库**，数据存在 RAM 里，读写速度极快（微秒级，比磁盘快 100 倍以上）。

支持多种数据结构：

| 结构 | 类比 | 用途 |
|------|------|------|
| String | 普通变量 | 缓存、计数器 |
| Hash | Python dict | 存储对象 |
| List | Python list | 消息队列 |
| Set | Python set | 去重、标签 |
| Sorted Set | 带分数的set | 排行榜、限速计数 |
| Stream | 消息流 | 日志收集 |

## 8.2 Redis 在 ChipWise 的用途

ChipWise 项目用 Redis 做了 5 件事，分布在不同 DB：

```
Redis DB 0：应用缓存 + 会话
    session:{user_id}:{session_id}  → 对话历史（TTL 1800s）
    gptcache:*                      → 语义缓存（TTL 3600-14400s）
    ratelimit:{user_id}:minute      → 限速计数器

Redis DB 1：Celery 任务
    _kombu/*                        → 任务队列
    celery-task-meta-{task_id}      → 任务结果
    task:progress:{task_id}         → 实时进度（TTL 86400s）
```

## 8.3 Python 操作 Redis

```python
import redis.asyncio as aioredis

# 连接
redis_client = aioredis.Redis(
    host="localhost",
    port=6379,
    db=0,
    password="your_password",
    encoding="utf-8",
    decode_responses=True,  # 自动解码bytes→str
)

# ── String 操作 ──
await redis_client.set("key", "value")
await redis_client.set("key", "value", ex=3600)  # TTL 3600秒
value = await redis_client.get("key")
await redis_client.delete("key")
await redis_client.incr("counter")   # 原子自增（限速用）

# ── Hash 操作 ──
await redis_client.hset("user:123", mapping={
    "name": "张三",
    "role": "admin"
})
name = await redis_client.hget("user:123", "name")
all_fields = await redis_client.hgetall("user:123")

# ── List 操作 ──
await redis_client.lpush("queue", "task1")  # 左边插入
await redis_client.rpush("queue", "task2")  # 右边插入
task = await redis_client.lpop("queue")     # 左边弹出

# ── Sorted Set 操作（限速用）──
now = time.time()
# 添加元素，score是时间戳
await redis_client.zadd("ratelimit:user1:minute", {str(uuid4()): now})
# 删除60秒前的记录
await redis_client.zremrangebyscore("ratelimit:user1:minute", 0, now - 60)
# 统计当前窗口内的请求数
count = await redis_client.zcard("ratelimit:user1:minute")
```

## 8.4 语义缓存（SemanticCache）

ChipWise 的核心优化：相似的问题直接返回缓存答案，不再调用 LLM。

原理：
```
"STM32的工作电压"  →  向量 [0.21, 0.85, ...]
"STM32供电电压是多少" →  向量 [0.22, 0.83, ...]
                         ↑ 余弦相似度 > 0.95 → 命中缓存！
```

实现逻辑（`src/cache/semantic_cache.py`）：
```python
class SemanticCache:
    async def get(self, query: str) -> str | None:
        # 1. 把查询向量化
        query_vec = await self.embedding.embed(query)
        
        # 2. 在Redis中搜索相似向量（或在Milvus中搜索）
        cached_keys = await redis.keys("gptcache:query:*")
        for key in cached_keys:
            cached_vec = await redis.get(key)
            similarity = cosine_similarity(query_vec, cached_vec)
            if similarity > 0.95:  # 高相似度 = 缓存命中
                # 取对应的response
                response_key = key.replace("query", "response")
                return await redis.get(response_key)
        return None

    async def set(self, query: str, response: str) -> None:
        query_vec = await self.embedding.embed(query)
        key_id = uuid4()
        # 存查询向量 + 响应结果
        await redis.set(f"gptcache:query:{key_id}", serialize(query_vec), ex=3600)
        await redis.set(f"gptcache:response:{key_id}", response, ex=3600)
```

## 8.5 限速（Rate Limiting）

ChipWise 用滑动窗口算法限速：

```python
async def check_rate_limit(user_id: str, redis: Redis) -> bool:
    """返回 True 表示超限"""
    now = time.time()
    key = f"ratelimit:{user_id}:minute"
    
    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, now - 60)   # 删除60秒前的记录
    pipe.zadd(key, {str(uuid4()): now})         # 添加本次请求
    pipe.zcard(key)                              # 统计数量
    pipe.expire(key, 60)                         # 设置TTL
    results = await pipe.execute()
    
    current_count = results[2]
    return current_count > 30  # 每分钟最多30次

# 对比其他算法：
# 固定窗口：简单，但存在边界问题（前30 + 后30 = 60次/2秒）
# 滑动窗口（上述）：精准，Redis有序集合天然支持
# 令牌桶：允许突发流量，平滑限速
# 漏桶：严格匀速，不允许突发
```

## 8.6 会话管理

```python
import json

async def save_session(
    redis: Redis, 
    user_id: str, 
    session_id: str,
    messages: list[dict]
) -> None:
    key = f"session:{user_id}:{session_id}"
    # 只保留最近10轮对话
    messages = messages[-20:]  # 10轮 = 20条消息（user+assistant各1条）
    await redis.set(key, json.dumps(messages), ex=1800)  # TTL 30分钟

async def get_session(
    redis: Redis,
    user_id: str,
    session_id: str
) -> list[dict]:
    key = f"session:{user_id}:{session_id}"
    data = await redis.get(key)
    if data:
        await redis.expire(key, 1800)  # 活跃时刷新TTL
        return json.loads(data)
    return []
```

## 8.7 Redis 持久化与高可用

| 方式 | 原理 | 优缺点 |
|------|------|-------|
| RDB（快照） | 定期把内存dump到磁盘 | 恢复快，但可能丢失最近数据 |
| AOF（追加日志） | 每次写操作都记录命令 | 数据安全，但文件大，恢复慢 |
| RDB+AOF | 混合 | 推荐生产配置 |

ChipWise 配置：`redis-server --maxmemory 3gb --maxmemory-policy allkeys-lru`

`allkeys-lru` = 内存满了就淘汰最久未使用的 key（适合缓存场景）。

---

# 第9章 向量数据库 Milvus

## 9.1 为什么需要向量数据库？

传统数据库存的是**精确数据**，只能做精确匹配：
```sql
SELECT * FROM chips WHERE name = 'STM32F4';  -- 精确匹配
```

但 AI 应用需要**语义搜索**：
```
用户问："低功耗ARM芯片"
→ 应该找到 STM32L4、STM32U5 等（即使关键词不完全匹配）
→ 传统SQL做不到
```

**向量数据库的解法**：
1. 把文本转成高维向量（嵌入向量 Embedding）
2. 语义相似 = 向量距离近
3. 搜索时找距离最近的向量

```
"低功耗ARM" → [0.21, -0.85, 0.33, ...] (1024维向量)
"STM32L4低功耗" → [0.22, -0.83, 0.31, ...] ← 很近！
"LED灯泡规格" → [-0.55, 0.12, 0.78, ...] ← 很远！
```

## 9.2 向量相似度算法

| 算法 | 公式 | 特点 |
|------|------|------|
| 余弦相似度 | cos(θ) = A·B / (|A||B|) | 对向量长度不敏感，最常用 |
| 内积（IP） | A·B | BGE-M3推荐，性能最好 |
| 欧氏距离（L2） | √Σ(aᵢ-bᵢ)² | 对长度敏感 |

## 9.3 HNSW 索引原理

Milvus 使用 **HNSW（Hierarchical Navigable Small World）** 索引加速向量搜索。

原理类比：图书馆找书
```
第3层（高速公路）：[区域A] [区域B] [区域C]
                        ↓ 找到大概区域
第2层（干道）：[书架1] [书架2] ... [书架10]
                        ↓ 找到具体书架
第1层（步行）：[书1][书2]...[书100]
                        ↓ 找到书
第0层（数据）：精确位置
```

ChipWise 配置：
```python
index_params = {
    "index_type": "HNSW",
    "metric_type": "IP",      # 使用内积
    "params": {
        "M": 16,              # 每个节点最多连接数（越大越准确，越慢）
        "efConstruction": 256  # 建索引时搜索范围（越大越准确）
    }
}
# 搜索时
search_params = {"ef": 128}   # 搜索时的范围（越大越准确，越慢）
```

## 9.4 BGE-M3 混合检索

BGE-M3 特点：**一次调用同时产生稠密向量 + 稀疏向量**

```
文本 → BGE-M3 → 稠密向量(1024维) + 稀疏向量(词袋)
                    ↓                    ↓
              语义相似度搜索          关键词精确匹配
                    ↓                    ↓
                  Milvus hybrid_search 融合
                         ↓
                    RRF 重排融合结果
```

- **稠密向量**：语义层面的相似（即使词不同，意思类似也能找到）
- **稀疏向量**：关键词层面（专业术语 "STM32F407" 精确匹配）
- **混合**：两者互补，效果最好

```python
# Milvus 混合搜索代码
from pymilvus import AnnSearchRequest, RRFRanker, Collection

collection = Collection("chip_chunks")

dense_req = AnnSearchRequest(
    data=[dense_vector],        # 稠密向量
    anns_field="dense_vector",
    param={"metric_type": "IP", "params": {"ef": 128}},
    limit=20
)

sparse_req = AnnSearchRequest(
    data=[sparse_vector],       # 稀疏向量
    anns_field="sparse_vector",
    param={"metric_type": "IP"},
    limit=20
)

results = collection.hybrid_search(
    reqs=[dense_req, sparse_req],
    rerank=RRFRanker(k=60),    # RRF融合排序
    limit=10,
    output_fields=["chunk_id", "text", "source"]
)
```

## 9.5 RAG 检索增强生成流程

这是 ChipWise 的核心能力，面试要能讲清楚：

```
离线阶段（文档入库）：
PDF文档 → 文本提取 → 分块(Chunk) → BGE-M3向量化 → Milvus存储

在线阶段（用户查询）：
用户问题 → QueryRewriter改写 → BGE-M3向量化
    ↓
Milvus混合搜索（Top-20候选块）
    ↓
bce-reranker重排（筛选Top-5最相关）
    ↓
把Top-5片段 + 用户问题 → LLM生成回答
    ↓
ResponseBuilder整理引用来源
    ↓
返回给用户（答案 + 来源引用）
```

**为什么要重排（Rerank）**？
- 向量搜索用的是近似算法（HNSW），结果不是完全按相关度排序
- 重排模型（Cross-Encoder）对每个候选块与问题做精确相关度评分
- 计算量大，所以先用向量搜索缩小范围到20个，再精排Top-5

---

# 第10章 异步编程与并发

## 10.1 Python 并发模型全景

Python 有三种并发方式，选错了性能很差：

```
任务类型         推荐方案          原理
─────────────────────────────────────────────────
IO密集型        asyncio协程       单线程，遇IO就切换
（网络请求、     或 多线程         多线程，GIL影响有限
  数据库查询）

CPU密集型       多进程            绕过GIL，真并行
（图像处理、     ProcessPoolExecutor
  数学计算）

混合型          asyncio +         协程处理IO
                run_in_executor   线程池处理CPU密集部分
```

**GIL（全局解释器锁）**：CPython 同一时刻只能执行一个线程的 Python 代码。这让多线程无法真正并行处理 CPU 密集任务，但对 IO 密集任务影响不大（等 IO 时会释放 GIL）。

## 10.2 asyncio 核心概念

```python
import asyncio

# 1. 协程（Coroutine）：用 async def 定义的函数
async def fetch_data(url: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    return response.text

# 2. 事件循环（Event Loop）：调度协程的引擎
async def main():
    result = await fetch_data("http://example.com")
    print(result)

asyncio.run(main())  # 启动事件循环

# 3. gather：并发执行多个协程
async def parallel_queries():
    # 串行：4秒
    r1 = await fetch_data(url1)
    r2 = await fetch_data(url2)
    
    # 并行：~2秒（取最慢的那个）
    r1, r2 = await asyncio.gather(
        fetch_data(url1),
        fetch_data(url2)
    )

# 4. Task：包装协程，可以取消
task = asyncio.create_task(fetch_data(url))
await asyncio.sleep(1)
task.cancel()  # 可以取消
```

## 10.3 FastAPI 的异步处理

```python
# async def：FastAPI 在 asyncio 事件循环中直接运行
@app.get("/fast")
async def fast_endpoint():
    await asyncio.sleep(0)     # 让出控制权，其他请求可以执行
    result = await db.query()  # 等待IO，不阻塞
    return result

# def（同步）：FastAPI 会放到线程池运行，不阻塞事件循环
@app.get("/slow")
def slow_endpoint():
    import time
    time.sleep(2)              # 同步sleep，但在线程池里所以不阻塞主循环
    return "done"

# 错误示范：在 async def 里用同步阻塞操作
@app.get("/wrong")
async def wrong_endpoint():
    import time
    time.sleep(2)   # ❌ 会阻塞整个事件循环！所有请求都被卡住
    return "done"
```

## 10.4 asyncio.gather vs asyncio.wait

```python
# gather：并发执行，全部完成才返回
results = await asyncio.gather(task1(), task2(), task3())

# gather 异常处理
results = await asyncio.gather(
    task1(), task2(), task3(),
    return_exceptions=True   # 某个失败不影响其他，返回异常对象而不是抛出
)
for r in results:
    if isinstance(r, Exception):
        print(f"失败: {r}")

# wait：更灵活，可以设置超时
done, pending = await asyncio.wait(
    [task1(), task2()],
    timeout=5.0,              # 5秒超时
    return_when=asyncio.FIRST_COMPLETED  # 任一完成就返回
)
```

## 10.5 异步上下文管理器和迭代器

```python
# 异步上下文管理器
async with httpx.AsyncClient() as client:
    response = await client.get(url)
# 相当于：
# client = httpx.AsyncClient()
# await client.__aenter__()
# try: ...
# finally: await client.__aexit__(...)

# 异步迭代器（流式输出时使用）
async for chunk in llm.stream("你好"):
    print(chunk, end="", flush=True)

# 异步生成器
async def token_stream(prompt: str):
    async for token in llm.stream(prompt):
        yield f"data: {token}\n\n"

# 在FastAPI SSE中使用
@app.get("/stream")
async def stream():
    return StreamingResponse(token_stream("请介绍STM32"), 
                            media_type="text/event-stream")
```

## 10.6 信号量（Semaphore）—— 控制并发数

ChipWise 用信号量限制同时调用 LLM 的请求数：

```python
# Redis 实现分布式信号量（src中的限制逻辑）
# 防止多个请求同时发给 35B 大模型，导致 OOM

import asyncio

# 本地信号量
llm_semaphore = asyncio.Semaphore(2)  # 最多2个并发

async def call_llm(prompt: str) -> str:
    async with llm_semaphore:  # 获取信号量，超出2个就等待
        return await llm.generate(prompt)

# 多个请求同时来
async def handle_requests():
    # 10个请求并发，但最多同时2个在调用LLM
    results = await asyncio.gather(*[
        call_llm(f"问题{i}") for i in range(10)
    ])
```

---

# 第11章 认证与授权

## 11.1 认证 vs 授权

- **认证（Authentication）**："你是谁？"— 验证身份（登录）
- **授权（Authorization）**："你能做什么？"— 验证权限（RBAC）

```
认证：用户名+密码 → 验证 → 颁发 Token
授权：请求携带 Token → 解析 → 判断有无权限
```

## 11.2 JWT（JSON Web Token）深度解析

JWT 是一种无状态的认证方案，格式：

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyMTIzIiwiZXhwIjoxNjk5MDAwMDAwfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c

[     Header      ][         Payload          ][   Signature   ]
```

三部分都是 Base64URL 编码（可以解码，不加密！）：

```python
import base64, json

# Header — 算法和类型
header = {"alg": "HS256", "typ": "JWT"}

# Payload — 携带的数据（称为"声明 Claims"）
payload = {
    "sub": "user123",       # subject：用户ID
    "exp": 1699000000,      # expiration：过期时间
    "iat": 1698900000,      # issued at：签发时间
    "role": "admin",        # 自定义字段
}

# Signature — 防篡改签名
import hmac, hashlib
signature = hmac.new(
    SECRET_KEY.encode(),
    (base64(header) + "." + base64(payload)).encode(),
    hashlib.sha256
).digest()
```

**JWT 的关键特性**：
- ✅ **无状态**：服务器不存储 Token，通过签名验证
- ✅ **自包含**：携带用户信息，无需查数据库
- ❌ **不能撤销**：Token 泄露后在过期前无法无效化（需要黑名单）
- ❌ **Payload 可见**：不要放密码等敏感信息

## 11.3 ChipWise 的 JWT 实现

```python
from datetime import datetime, timedelta
import jwt   # PyJWT库

SECRET_KEY = "your-secret-key"  # 实际从环境变量读取
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = timedelta(hours=8)
REFRESH_TOKEN_EXPIRE = timedelta(days=30)

def create_access_token(user_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.utcnow() + ACCESS_TOKEN_EXPIRE,
        "iat": datetime.utcnow(),
        "type": "access",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + REFRESH_TOKEN_EXPIRE,
        "type": "refresh",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token 已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token 无效")
```

### Token 刷新流程

```
用户登录
    ↓
返回：access_token（短期，8小时） + refresh_token（长期，30天）
    ↓
前端每次请求带 access_token
    ↓
access_token 过期
    ↓
前端用 refresh_token 请求 /api/v1/auth/refresh
    ↓
服务器验证 refresh_token，返回新的 access_token
    ↓
继续使用，无需重新登录
```

## 11.4 OAuth2 与 OIDC

**OAuth2** 是**授权**协议（不是认证）：让第三方应用代表用户访问资源，而不暴露密码。

场景：用"微信"登录第三方网站——你把微信的"头像/昵称"访问权授权给了第三方网站，但不给密码。

**OIDC（OpenID Connect）** = OAuth2 + 用户身份认证，是 OAuth2 的扩展。

ChipWise 的 SSO（单点登录）就基于 OIDC：

```
用户点击"企业微信登录"
      ↓
ChipWise 生成 state（CSRF防护）和 nounce
      ↓
302 重定向到企业微信/Keycloak 的登录页
      ↓
用户在企业微信输入账号密码
      ↓
企业微信 302 回调 /api/v1/auth/sso/callback?code=xxx&state=xxx
      ↓
验证 state（防CSRF）
      ↓
用 code 换 access_token（发请求到企业微信服务器）
      ↓
用 access_token 获取用户信息
      ↓
JIT Provisioning：在本地数据库创建/更新用户
      ↓
颁发 ChipWise JWT，重定向到前端
```

```python
# src/auth/sso/providers/keycloak.py 关键逻辑
class KeycloakProvider(BaseSSOProvider):
    def get_authorization_url(self) -> tuple[str, str]:
        state = secrets.token_urlsafe(32)      # 随机state，防CSRF
        nonce = secrets.token_urlsafe(32)      # 防重放攻击
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid profile email",
            "state": state,
            "nonce": nonce,
        }
        url = f"{self.auth_url}?{urlencode(params)}"
        return url, state

    async def exchange_code(self, code: str) -> UserInfo:
        # 用code换token
        response = await httpx.post(self.token_url, data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
        })
        tokens = response.json()
        # 解析ID Token获取用户信息
        id_token = jwt.decode(tokens["id_token"], options={"verify_signature": False})
        return UserInfo(
            provider_id=id_token["sub"],
            email=id_token.get("email"),
            name=id_token.get("name"),
        )
```

## 11.5 RBAC 角色权限控制

**RBAC（Role-Based Access Control）** = 基于角色的权限控制

ChipWise 三个角色：`admin > user > viewer`

```python
from enum import Enum

class Role(str, Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"

ROLE_PERMISSIONS = {
    Role.ADMIN:  ["read", "write", "delete", "manage_users"],
    Role.USER:   ["read", "write"],
    Role.VIEWER: ["read"],
}

# FastAPI 权限依赖
def require_role(required_role: Role):
    async def check_role(user: User = Depends(get_current_user)) -> User:
        role_priority = {Role.VIEWER: 0, Role.USER: 1, Role.ADMIN: 2}
        if role_priority[user.role] < role_priority[required_role]:
            raise HTTPException(403, f"需要 {required_role} 权限")
        return user
    return check_role

# 使用：只有admin可以调用
@router.delete("/api/v1/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    user: User = Depends(require_role(Role.ADMIN))
):
    ...
```

## 11.6 密码安全存储

**绝对不能明文存密码！** 要用单向哈希 + 盐：

```python
from passlib.context import CryptContext

# bcrypt：专为密码设计的哈希算法，慢是故意的（防暴力破解）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)
    # 结果类似：$2b$12$Kv0KtJf3zZQj... (每次不同，因为盐随机)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# 登录验证
async def authenticate_user(username: str, password: str) -> User | None:
    user = await get_user_by_username(username)
    if not user:
        # 即使用户不存在也要执行verify，防止时序攻击
        pwd_context.verify(password, "fake_hash")
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
```

---

# 第12章 Docker 与容器化

## 12.1 Docker 是什么？

Docker 解决"在我机器上能跑"的问题。

**虚拟机 vs 容器**：

```
虚拟机：
┌─────────────────────────────────┐
│   App A    │   App B    │  App C │
├────────────┼────────────┼────────┤
│  OS(4GB)   │  OS(4GB)   │OS(4GB) │
├────────────┴────────────┴────────┤
│        Hypervisor                │
├──────────────────────────────────┤
│        物理机 OS + 硬件           │
└──────────────────────────────────┘
每个VM有完整OS，重（GB级），启动慢（分钟）

容器（Docker）：
┌──────────────────────────────────┐
│  App A  │  App B  │  App C       │
├─────────┼─────────┼──────────────┤
│  Lib A  │  Lib B  │  Lib C       │
├─────────┴─────────┴──────────────┤
│        Docker Engine（共享OS内核）│
├──────────────────────────────────┤
│        物理机 OS + 硬件           │
└──────────────────────────────────┘
共享OS内核，轻（MB级），启动快（秒级）
```

## 12.2 Dockerfile 解析

ChipWise 的 BGE-M3 嵌入服务 Dockerfile：

```dockerfile
# Dockerfile.embedding

# 1. 基础镜像（Python 3.10 + 精简版）
FROM python:3.10-slim

# 2. 设置工作目录
WORKDIR /app

# 3. 先复制 requirements（利用Docker层缓存：只有requirements变才重建这层）
COPY requirements-services.txt .

# 4. 安装依赖（--no-cache-dir 减小镜像体积）
RUN pip install --no-cache-dir -r requirements-services.txt

# 5. 复制应用代码
COPY services/embedding_service.py .

# 6. 声明暴露的端口（文档作用，实际由docker-compose映射）
EXPOSE 8001

# 7. 启动命令
CMD ["uvicorn", "embedding_service:app", "--host", "0.0.0.0", "--port", "8001"]
```

### Dockerfile 最佳实践

```dockerfile
# ✅ 多阶段构建（减小生产镜像大小）
FROM python:3.10 AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

FROM python:3.10-slim AS runtime
COPY --from=builder /install /usr/local   # 只复制安装结果，不带编译工具
COPY src/ /app/src/
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]

# ✅ 使用 .dockerignore（类似 .gitignore）
# .dockerignore:
# __pycache__/
# .git/
# .venv/
# *.pyc
# data/
# logs/
```

## 12.3 Docker Compose 完全解析

Docker Compose 用一个 YAML 文件管理多个容器，ChipWise 的 `docker-compose.yml`：

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:15-alpine      # 使用官方镜像
    container_name: chipwise-postgres
    
    ports:
      - "5432:5432"                # 宿主机:容器 端口映射
    
    environment:
      POSTGRES_DB: chipwise
      POSTGRES_USER: chipwise
      POSTGRES_PASSWORD: ${PG_PASSWORD}    # 从环境变量读取（安全！）
    
    volumes:
      - pg_data:/var/lib/postgresql/data   # 数据持久化到named volume
    
    deploy:
      resources:
        limits:
          cpus: "2.0"             # CPU限制
          memory: 4G              # 内存限制
    
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U chipwise"]
      interval: 10s               # 每10秒检查一次
      timeout: 5s                 # 超时5秒算失败
      retries: 5                  # 失败5次才标记unhealthy

volumes:
  pg_data:                        # 定义named volume（重启容器数据不丢失）
```

### Docker 网络

同一个 Compose 文件里的容器默认在同一个**桥接网络**中，可以通过**服务名**互相访问：

```python
# FastAPI 连接 Postgres（容器间通信）
DATABASE_URL = "postgresql://chipwise:password@postgres:5432/chipwise"
#                                               ↑服务名，不是localhost！

# 从宿主机连接（端口映射后）
DATABASE_URL = "postgresql://chipwise:password@localhost:5432/chipwise"
```

### 常用 Docker 命令

```bash
# 启动所有服务（后台运行）
docker-compose up -d

# 查看运行状态
docker-compose ps

# 查看某个服务的日志
docker-compose logs -f postgres

# 进入容器
docker exec -it chipwise-postgres bash

# 重启某个服务
docker-compose restart redis

# 停止并删除（保留volumes数据）
docker-compose down

# 停止并删除（包括volumes！危险！）
docker-compose down -v

# 重新构建镜像
docker-compose build embedding-service

# 查看资源占用
docker stats
```

## 12.4 容器化的好处总结

| 问题 | Docker 解决方式 |
|------|---------------|
| "在我机器上能跑" | 镜像包含完整依赖，环境一致 |
| 依赖冲突 | 每个容器独立文件系统 |
| 部署流程复杂 | `docker-compose up` 一键启动 |
| 版本管理混乱 | 镜像有 tag，可回滚 |
| 资源隔离 | CPU/内存限制，一个服务崩溃不影响其他 |

---

# 第13章 Celery 任务队列

## 13.1 为什么需要任务队列？

用户上传一个 100MB 的 PDF：
- 提取文本：5秒
- 提取表格：20秒  
- LLM 参数提取：60秒
- 向量化并存入 Milvus：30秒
- 总共：~2分钟

如果同步处理：用户等 2 分钟，HTTP 连接超时，用户体验极差。

**任务队列解法**：
```
用户上传 PDF
    ↓
FastAPI 立刻返回 {"task_id": "abc123", "status": "queued"}（0.1秒）
    ↓
后台 Celery Worker 异步处理文件
    ↓
用户轮询 GET /api/v1/tasks/abc123 查看进度
    ↓
处理完成通知用户
```

## 13.2 Celery 架构

```
FastAPI（生产者）
    │  publish task
    ▼
Redis（消息 Broker）
    │  consume task
    ▼
Celery Worker（消费者）
    │  store result
    ▼
Redis（Result Backend）
    │
    ▼
FastAPI GET /tasks/{id} 返回结果
```

## 13.3 ChipWise 的 Celery 任务链

文档处理是一个**任务链**（chain），前一个任务的输出是下一个任务的输入：

```python
# src/ingestion/tasks.py
from celery import chain

@celery_app.task(bind=True, queue="default")
def download_document(self, document_id: str) -> str:
    """下载文档，返回本地路径"""
    ...

@celery_app.task(bind=True, queue="default")
def extract_pdf(self, local_path: str) -> dict:
    """PDF文本提取"""
    ...

@celery_app.task(bind=True, queue="heavy")   # 重计算任务用heavy队列
def extract_tables(self, extracted: dict) -> dict:
    """3层表格提取（PaddleOCR）"""
    ...

@celery_app.task(bind=True, queue="embedding")
def embed_and_store(self, processed: dict) -> dict:
    """向量化并存入Milvus"""
    ...

# 组成任务链
def ingest_document(document_id: str):
    result = chain(
        download_document.s(document_id),
        extract_pdf.s(),
        extract_tables.s(),
        embed_and_store.s(),
    ).apply_async()
    return result.id    # 返回任务ID给用户
```

### 任务重试与错误处理

```python
@celery_app.task(
    bind=True,
    queue="default",
    max_retries=3,              # 最多重试3次
    default_retry_delay=2,      # 初始等待2秒
)
def reliable_task(self, data: dict):
    try:
        return process(data)
    except TemporaryError as e:
        # 指数退避重试：2s, 4s, 8s
        retry_count = self.request.retries
        wait = 2 ** retry_count
        raise self.retry(exc=e, countdown=min(wait, 60))
    except PermanentError as e:
        # 不重试，直接标记失败
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise
```

### 进度上报

```python
@celery_app.task(bind=True)
def process_document(self, doc_id: str):
    total_steps = 4
    
    self.update_state(state="PROGRESS", meta={"progress": 0, "step": "下载中"})
    download()
    
    self.update_state(state="PROGRESS", meta={"progress": 25, "step": "提取文本"})
    extract()
    
    self.update_state(state="PROGRESS", meta={"progress": 50, "step": "向量化"})
    embed()
    
    self.update_state(state="PROGRESS", meta={"progress": 75, "step": "存储中"})
    store()
    
    return {"progress": 100, "status": "success"}
```

## 13.4 三个 Worker 分工

```
Worker1 (default, embedding 队列):
    - 下载文档
    - 参数提取（LLM调用）
    - 向量化（BGE-M3调用）
    
Worker2 (heavy 队列):
    - PaddleOCR表格提取
    - 3GB内存占用，按需加载模型
    
Worker3 (crawler 队列):
    - Playwright网络爬虫
    - 每个域名限速，防ban

Beat调度器:
    - 定时触发爬虫（每天凌晨2点）
    - cron 表达式："0 2 * * *"
```

---

# 第14章 安全：OWASP Top 10 实战

## 14.1 OWASP Top 10 概览

OWASP（Open Web Application Security Project）是权威的 Web 安全标准，面试必考：

| 序号 | 漏洞类型 | ChipWise 防御措施 |
|------|---------|-----------------|
| A01 | 访问控制失效 | RBAC + JWT + Depends权限检查 |
| A02 | 加密失败 | bcrypt密码哈希，HTTPS传输，secrets存环境变量 |
| A03 | 注入 | SQLAlchemy ORM参数化，Pydantic输入校验 |
| A04 | 不安全设计 | 需求阶段安全设计，威胁建模 |
| A05 | 安全配置错误 | Docker限制资源，关闭调试信息 |
| A06 | 易受攻击组件 | requirements.txt版本锁定，定期更新 |
| A07 | 身份认证失败 | JWT签名验证，Token过期，限速 |
| A08 | 软件完整性失败 | SHA256文档去重，镜像签名 |
| A09 | 日志监控不足 | TraceContext全链路追踪，结构化日志 |
| A10 | SSRF | 验证外部URL，内网访问限制 |

## 14.2 SQL 注入防御

```python
# ❌ 危险：字符串拼接SQL
name = request.query_params.get("name")
query = f"SELECT * FROM chips WHERE name = '{name}'"
# 攻击者输入：'; DROP TABLE chips; --

# ✅ 安全：SQLAlchemy 参数化查询（自动转义）
stmt = select(Chip).where(Chip.name == name)  # 参数化，安全

# ✅ 安全：原生SQL也用参数化
result = await session.execute(
    text("SELECT * FROM chips WHERE name = :name"),
    {"name": name}   # 绑定参数，不是字符串拼接
)
```

## 14.3 XSS 防御

```python
# 后端永远不信任用户输入
from html import escape

# ❌ 危险：直接返回用户输入的HTML
@app.get("/greet")
async def greet(name: str):
    return HTMLResponse(f"<h1>你好，{name}！</h1>")
# 攻击者输入：<script>document.cookie</script>

# ✅ 安全：转义HTML特殊字符，或只返回JSON
@app.get("/greet")
async def greet(name: str):
    return {"message": f"你好，{escape(name)}！"}
```

## 14.4 CSRF 防御

ChipWise SSO 使用 state 参数防 CSRF：

```python
# 生成随机 state
state = secrets.token_urlsafe(32)   # 32字节随机数，不可预测
_STATE_STORE[state] = {"created_at": time.time()}

# 重定向到 IdP（带state）
return RedirectResponse(f"{auth_url}?state={state}&...")

# 回调时验证 state
async def sso_callback(code: str, state: str):
    if state not in _STATE_STORE:
        raise HTTPException(400, "无效的 state，可能是 CSRF 攻击")
    
    # 检查过期（10分钟内有效）
    stored = _STATE_STORE.pop(state)
    if time.time() - stored["created_at"] > 600:
        raise HTTPException(400, "state 已过期")
    
    # 继续处理...
```

## 14.5 敏感信息保护

```python
# ❌ 危险：把密钥硬编码在代码里
SECRET_KEY = "my-super-secret-key-12345"

# ✅ 安全：从环境变量读取
import os
SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY 环境变量未设置")

# ✅ 安全：Pydantic Settings（ChipWise方式）
class Settings(BaseSettings):
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    pg_password: str = Field(..., env="PG_PASSWORD")
    # 如果环境变量不存在，启动时报错

# .env 文件（不提交到git！）
# JWT_SECRET_KEY=randomly-generated-64-char-string
# PG_PASSWORD=strong-password-here
```

## 14.6 输入验证

```python
from pydantic import BaseModel, Field, field_validator
import re

class DocumentUploadRequest(BaseModel):
    filename: str = Field(..., max_length=255)
    
    @field_validator("filename")
    @classmethod
    def safe_filename(cls, v: str) -> str:
        # 防止路径遍历攻击
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("文件名包含非法字符")
        if not re.match(r'^[\w\-. ]+$', v):
            raise ValueError("文件名包含特殊字符")
        return v

# 文件类型验证（不信任 Content-Type，检查Magic Bytes）
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx"}
MAGIC_BYTES = {
    b"%PDF": ".pdf",
    b"PK\x03\x04": ".docx/.xlsx",
}

async def validate_file(file: UploadFile) -> None:
    # 检查扩展名
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"不支持的文件类型: {ext}")
    
    # 检查文件头（Magic Bytes）
    header = await file.read(8)
    await file.seek(0)  # 重置游标
    valid = any(header.startswith(magic) for magic in MAGIC_BYTES)
    if not valid:
        raise HTTPException(400, "文件内容与扩展名不匹配")
```

---

# 第15章 可观测性

## 15.1 可观测性三支柱

可观测性（Observability）= 从系统外部推断内部状态的能力，三个工具：

| 支柱 | 作用 | ChipWise实现 |
|------|------|------------|
| **日志**（Logs） | 记录发生了什么 | `src/observability/logger.py` |
| **追踪**（Traces） | 记录一个请求经过了哪些组件 | `src/observability/trace_context.py` |
| **指标**（Metrics） | 量化系统状态（QPS、延迟、错误率） | Prometheus + Grafana |

## 15.2 结构化日志

不要用 `print`，用结构化日志（JSON 格式，便于机器解析）：

```python
import logging
import json

# 配置结构化日志
class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": getattr(record, "trace_id", None),
        })

logger = logging.getLogger("chipwise")
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

# 使用
logger.info("查询处理完成", extra={"trace_id": "uuid-123", "duration_ms": 245})
# 输出：{"timestamp": "...", "level": "INFO", "message": "查询处理完成", "trace_id": "uuid-123"}
```

## 15.3 TraceContext（分布式追踪）

每个请求生成全局唯一 trace_id，记录经过的每个阶段：

```python
# src/observability/trace_context.py
import time
import json
from pathlib import Path

class TraceContext:
    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.stages: list[dict] = []
        self.start_time = time.time()
    
    def record_stage(self, name: str, metadata: dict = None):
        self.stages.append({
            "stage": name,
            "timestamp": time.time() - self.start_time,
            "metadata": metadata or {}
        })
    
    def save(self):
        with open("logs/traces.jsonl", "a") as f:
            f.write(json.dumps({
                "trace_id": self.trace_id,
                "total_ms": (time.time() - self.start_time) * 1000,
                "stages": self.stages
            }) + "\n")

# 在请求处理中使用
async def process_query(query: str, trace_id: str):
    trace = TraceContext(trace_id)
    
    trace.record_stage("cache_check")
    cached = await cache.get(query)
    if cached:
        trace.record_stage("cache_hit")
        return cached
    
    trace.record_stage("embedding_start")
    vec = await embed(query)
    trace.record_stage("embedding_done", {"vector_dim": len(vec)})
    
    trace.record_stage("search_start")
    results = await milvus.search(vec)
    trace.record_stage("search_done", {"result_count": len(results)})
    
    trace.save()
    return results
```

traces.jsonl 中的一条记录：
```json
{"trace_id": "abc123", "total_ms": 1234, "stages": [
  {"stage": "cache_check", "timestamp": 0.001},
  {"stage": "embedding_start", "timestamp": 0.002},
  {"stage": "embedding_done", "timestamp": 0.045, "metadata": {"vector_dim": 1024}},
  {"stage": "search_start", "timestamp": 0.046},
  {"stage": "search_done", "timestamp": 0.123, "metadata": {"result_count": 20}}
]}
```

## 15.4 健康检查接口

ChipWise 的三个健康检查端点（`src/api/routers/health.py`）：

```python
@router.get("/health")
async def health():
    """简单存活检查，Nginx upstream 用"""
    return {"status": "ok", "version": APP_VERSION}

@router.get("/liveness")
async def liveness():
    """K8s liveness probe：进程是否活着"""
    return {"status": "alive"}

@router.get("/readiness")
async def readiness():
    """K8s readiness probe：是否可以接收流量"""
    checks = {}
    overall = "healthy"
    
    # 检查 PostgreSQL
    try:
        await db.execute("SELECT 1")
        checks["postgres"] = "healthy"
    except Exception:
        checks["postgres"] = "unhealthy"
        overall = "degraded"
    
    # 检查 Redis
    try:
        await redis.ping()
        checks["redis"] = "healthy"
    except Exception:
        checks["redis"] = "unhealthy"
        overall = "degraded"
    
    # 检查 LM Studio（可选，不影响基础功能）
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get("http://localhost:1234/v1/models", timeout=2)
        checks["llm"] = "healthy" if r.status_code == 200 else "unavailable"
    except Exception:
        checks["llm"] = "unavailable"
        # 注意：LLM 不可用只是 degraded，不是 unhealthy
    
    status_code = 200 if overall != "unhealthy" else 503
    return JSONResponse({"status": overall, "checks": checks}, status_code=status_code)

---

# 第16章 大厂面试题完全解析

> 以下全部是字节/腾讯/阿里/美团后端面试真题，附详细答案。

---

## 16.1 HTTP 与网络

### Q: HTTP 和 HTTPS 的区别？

**答**：
- HTTP 是明文传输，HTTPS = HTTP + TLS 加密层
- HTTPS 防止三种攻击：**窃听**（加密）、**篡改**（完整性校验）、**仿冒**（证书认证）
- HTTPS 需要 CA 颁发的 SSL 证书
- 性能：HTTPS 多了 TLS 握手开销，但 HTTP/2（通常基于HTTPS）的多路复用性能更好
- 端口：HTTP 默认 80，HTTPS 默认 443

---

### Q: GET 和 POST 的区别？

**答**：

| 维度 | GET | POST |
|------|-----|------|
| 语义 | 获取资源 | 创建/提交资源 |
| 参数位置 | URL（?key=value） | Request Body |
| 安全性 | URL 会被日志记录，不适合密码 | Body 传输，相对安全 |
| 长度限制 | URL 有长度限制（~2000字符） | Body 无限制 |
| 幂等性 | ✅ 幂等 | ❌ 不幂等 |
| 缓存 | 可缓存 | 不可缓存 |

**注意**：GET 和 POST 本质上都是 HTTP 请求，安全性取决于 HTTPS，而非方法本身。

---

### Q: 一次 HTTP 请求的完整过程？

**答**：
1. **DNS 解析**：域名 → IP（优先查本地缓存 → hosts文件 → DNS服务器）
2. **TCP 三次握手**：建立可靠连接
   - SYN → SYN-ACK → ACK
3. **TLS 握手**（HTTPS）：协商加密算法，验证证书，交换密钥
4. **发送 HTTP 请求**：请求行 + 请求头 + 请求体
5. **服务器处理**：路由匹配 → 业务处理 → 数据库查询
6. **返回 HTTP 响应**：状态行 + 响应头 + 响应体
7. **TCP 四次挥手**（或 Keep-Alive 保持连接）
8. **浏览器渲染**（HTML）或前端处理 JSON

---

### Q: TCP 三次握手和四次挥手是什么？为什么握手3次，挥手4次？

**答**：

**三次握手**（建立连接）：
```
客户端           服务器
  │──── SYN ────▶│          ① 我想连你
  │◀─── SYN-ACK─┤          ② 我也想连你
  │──── ACK ────▶│          ③ 好的，连通了
```
为什么3次？最少需要3次才能确认双方都能收发数据。

**四次挥手**（断开连接）：
```
客户端           服务器
  │──── FIN ────▶│          ① 我发完了，准备关闭
  │◀─── ACK ────┤           ② 我知道了（但服务器可能还有数据没发完）
  │◀─── FIN ────┤           ③ 我也发完了，可以关闭了
  │──── ACK ────▶│          ④ 好的，双方都关闭
```
为什么4次？因为 FIN 和 ACK 发送方不同，不能像握手那样合并。

---

### Q: 什么是 TCP 粘包问题？如何解决？

**答**：TCP 是字节流协议，没有消息边界概念。发送 "hello" 和 "world" 两条消息，接收方可能一次收到 "helloworld"（粘包）或分两次收到 "hel" "loworld"（拆包）。

解决方案：
1. **固定长度**：每条消息固定 N 字节
2. **分隔符**：用特殊字符（如 \n）分隔消息
3. **长度前缀**：消息头部包含数据长度（HTTP 的 Content-Length 就是这个思路）
4. **应用层协议**：HTTP 自己就解决了这个问题

---

## 16.2 数据库

### Q: 事务的 ACID 特性是什么？

**答**：
- **A（Atomicity 原子性）**：事务中的所有操作要么全成功，要么全失败回滚。例：转账时扣款和收款必须同时成功。
- **C（Consistency 一致性）**：事务执行前后，数据库从一个合法状态变为另一个合法状态。例：转账后总金额不变。
- **I（Isolation 隔离性）**：并发执行的事务互相不干扰。
- **D（Durability 持久性）**：提交后的事务即使系统崩溃也不会丢失（WAL 预写日志保证）。

---

### Q: 事务隔离级别有哪些？分别解决了什么问题？

**答**：

| 隔离级别 | 脏读 | 不可重复读 | 幻读 | 性能 |
|---------|------|-----------|------|------|
| READ UNCOMMITTED | ✅可能 | ✅可能 | ✅可能 | 最高 |
| READ COMMITTED | ❌防止 | ✅可能 | ✅可能 | 高 |
| REPEATABLE READ | ❌防止 | ❌防止 | ✅可能 | 中 |
| SERIALIZABLE | ❌防止 | ❌防止 | ❌防止 | 最低 |

- **脏读**：读到其他事务未提交的数据
- **不可重复读**：同一事务内两次读同一行，数据不同（被其他事务修改并提交）
- **幻读**：同一事务内两次查询，结果集行数不同（其他事务插入了新行）

PostgreSQL 默认是 `READ COMMITTED`，MySQL InnoDB 默认是 `REPEATABLE READ`。

---

### Q: 索引为什么能提高查询速度？什么时候不该建索引？

**答**：

索引原理：B-Tree 结构，把 O(n) 全表扫描降为 O(log n)。

**适合建索引**：
- 经常出现在 WHERE 条件的列
- JOIN 的关联列（外键）
- ORDER BY 的列
- 高选择性的列（值种类多，如 email，不适合 gender 这种只有2种值的）

**不该建索引**：
- 小表（全表扫描还更快）
- 频繁写入的列（写时要更新索引，降低写性能）
- 很少用于查询的列
- 低选择性的列（如 status 只有 active/inactive）

---

### Q: MySQL InnoDB 和 MyISAM 的区别？（或 PostgreSQL vs MySQL）

**答**（InnoDB vs MyISAM）：

| 特性 | InnoDB | MyISAM |
|------|--------|--------|
| 事务 | ✅ 支持 | ❌ 不支持 |
| 外键 | ✅ 支持 | ❌ 不支持 |
| 行锁 | ✅ 行级锁 | ❌ 表级锁 |
| 崩溃恢复 | ✅ WAL | ❌ 有风险 |
| 全文索引 | 5.6+ 支持 | ✅ 原生支持 |
| 适用场景 | 大多数场景 | 大量读、少量写的场景 |

---

### Q: 如何做数据库分库分表？

**答**：

**垂直分表**：把一张大表按列拆分，常用字段和不常用字段分开：
```
users 表 → users_basic（id, name, phone）+ users_profile（id, avatar, bio, ...)
```

**水平分表（Sharding）**：按行分，同结构的表分到多个物理表：
```
orders_2024_01, orders_2024_02 ... （按时间分）
users_00~users_99（按user_id % 100分）
```

**分库**：把不同的表/业务放到不同的数据库实例，降低单机压力。

**常见问题**：
- 分布式事务（2PC、Saga）
- 跨分片查询（聚合难）
- 分片键选择（避免热点）
- 扩容时重新分片（一致性哈希最小化迁移）

---

### Q: 什么是 N+1 查询问题？如何解决？

**答**：

```python
# N+1 问题示例
chips = session.query(Chip).all()     # 1次查询
for chip in chips:
    params = chip.parameters          # N次查询！每个chip都单独查一次
```

如果有 100 个 chip，就会产生 1 + 100 = 101 次 SQL 查询。

**解决方案**：
```python
# 方案1：JOIN 一次性加载（eager loading）
stmt = select(Chip).options(selectinload(Chip.parameters))
chips = await session.execute(stmt)   # 只有2次SQL：1次查chip，1次查所有parameters

# 方案2：批量查询
chip_ids = [c.id for c in chips]
params = session.query(Parameter).filter(Parameter.chip_id.in_(chip_ids)).all()
```

---

## 16.3 缓存

### Q: Redis 和 Memcached 的区别？

**答**：

| 维度 | Redis | Memcached |
|------|-------|-----------|
| 数据结构 | 多种（String/Hash/List/Set/ZSet/Stream） | 只有 String |
| 持久化 | ✅ RDB + AOF | ❌ 不持久化 |
| 集群 | Redis Cluster | 一致性哈希 |
| 原子操作 | ✅ Lua 脚本 | ❌ |
| 性能 | 稍慢（功能多） | 极快（功能少） |
| 适用场景 | 缓存 + 队列 + 会话等 | 纯缓存 |

**选 Redis**：需要持久化、需要复杂数据结构、需要发布订阅。

---

### Q: 缓存穿透、缓存击穿、缓存雪崩是什么？如何解决？

**答**：

**缓存穿透**：查询一个不存在的数据，每次都打到数据库。

```
攻击者大量请求 /chips/FAKE_ID → Redis Miss → DB Miss → DB压力
```

解决：
- **布隆过滤器**：快速判断Key是否存在，不存在直接返回
- **空值缓存**：把DB查出的null也缓存起来（TTL短一些）

---

**缓存击穿**：热点Key过期瞬间，大量请求同时穿透到数据库。

解决：
- **互斥锁**：只让一个请求查数据库，其他等待
- **逻辑过期**：不设 TTL，让后台异步刷新
- **永不过期**：对于极热数据

---

**缓存雪崩**：大量Key同时过期，或 Redis 宕机，所有请求打到数据库。

解决：
- **过期时间加随机抖动**：`TTL = base + random(0, 300)`
- **熔断器（Circuit Breaker）**：DB 压力过高时快速失败
- **Redis 高可用**：主从 + 哨兵 / Redis Cluster

---

### Q: 如何保证缓存和数据库的一致性？

**答**：

常见策略对比：

**Cache-Aside（旁路缓存，最常用）**：
- 读：先读缓存，miss 再读 DB，回填缓存
- 写：先写 DB，再**删除**缓存（不是更新）
- 为什么是删除不是更新？更新可能并发导致脏数据，删除后下次查询会重新回填

**Write-Through（直写）**：
- 写：同时写 DB 和缓存（同步）
- 优点：缓存总是最新的
- 缺点：写延迟高

**Write-Behind（异步回写）**：
- 写：先写缓存，异步批量写 DB
- 优点：写性能极高
- 缺点：有数据丢失风险

**最终一致性方案（分布式系统）**：
- Canal 监听 MySQL binlog → 更新缓存
- 消息队列保证最终一致

---

## 16.4 异步与并发

### Q: 进程、线程、协程的区别？

**答**：

| 维度 | 进程 | 线程 | 协程 |
|------|------|------|------|
| 资源 | 独立内存空间 | 共享进程内存 | 用户态，极轻量 |
| 切换开销 | 最大（内核调度） | 中等（内核调度） | 最小（用户态调度） |
| 数量 | 数百 | 数千 | 数十万 |
| 通信 | IPC（管道/共享内存） | 共享变量（需加锁） | 通过 yield/await |
| 崩溃影响 | 不影响其他进程 | 一个线程崩可能导致进程崩 | 在同一线程内 |
| Python GIL | 可以绕过 | 无法绕过（CPU密集无效） | 同线程，协作调度 |

---

### Q: Python 的 GIL 是什么？有什么影响？

**答**：

GIL（Global Interpreter Lock）是 CPython 的一个互斥锁，同一时刻只允许一个线程执行 Python 字节码。

**影响**：
- CPU 密集任务：多线程无效，因为同一时刻只有一个线程在运行
- IO 密集任务：等待 IO 时会释放 GIL，其他线程可以运行，多线程有效

**绕过 GIL**：
- `multiprocessing`（多进程）：每个进程有自己的 GIL
- `concurrent.futures.ProcessPoolExecutor`
- C 扩展（NumPy、pandas 的底层运算释放 GIL）

**asyncio 的定位**：不是绕过 GIL，而是通过单线程协程避免线程切换开销，适合 IO 密集场景。

---

### Q: 什么是死锁？如何避免？

**答**：

死锁 = 两个或多个进程互相等待对方释放资源，永远等下去。

```
线程A 持有锁1，等待锁2
线程B 持有锁2，等待锁1
→ 死锁！
```

必要条件（四个条件同时满足才会死锁，**Coffman 条件**）：
1. 互斥（资源同一时刻只能被一个进程占用）
2. 持有并等待（进程持有资源并等待其他资源）
3. 不可剥夺（资源不能被强制取走）
4. 循环等待（进程形成环形等待链）

**预防方法**：
- **有序加锁**：所有线程按相同顺序请求锁（破坏循环等待）
- **一次性申请所有锁**（破坏持有并等待）
- **超时放弃**：用 `lock.acquire(timeout=5)` 加超时
- **使用更高级的并发原语**：协程通常不需要锁

---

## 16.5 系统设计

### Q: 如何设计一个高并发的查询系统？（以 ChipWise 为例）

**答**（分层回答）：

**1. 接入层**：
- Nginx 负载均衡，轮询或加权策略
- 限速（Rate Limit）：防止单用户滥用，Redis 滑动窗口
- 熔断器：下游超时时快速失败，防级联崩溃

**2. 应用层**：
- FastAPI + asyncio：单线程处理大量并发 IO
- 信号量控制 LLM 并发数（防 OOM）
- 连接池：数据库连接池，避免每次重建连接

**3. 缓存层**：
- 语义缓存（Semantic Cache）：相似问题命中缓存，跳过 LLM
- Redis 会话缓存：减少数据库查询

**4. 数据层**：
- Milvus 向量索引（HNSW）：O(log n) 向量搜索
- PostgreSQL 索引优化：合理建索引
- 读写分离：主库写，从库读（水平扩展读能力）

**5. 异步处理**：
- 文档处理用 Celery 异步队列，不占用请求处理线程
- 预热：启动时预加载常用数据到缓存

---

### Q: 如何设计一个 JWT 认证系统？

**答**：

**完整流程**：
```
1. 用户 POST /auth/login { username, password }
2. 服务器验证密码（bcrypt.verify）
3. 生成 access_token（1小时，包含user_id、role）
4. 生成 refresh_token（30天，只含user_id）
5. refresh_token 存入 Redis（key: refresh:{user_id}，可随时撤销）
6. 返回两个 token

7. 前端每次请求带 Authorization: Bearer <access_token>
8. 服务器验证签名、检查过期时间

9. access_token 过期 → 用 refresh_token 换新 access_token
10. 服务器验证 refresh_token 在 Redis 中存在（若被撤销则不存在）
11. 生成新 access_token 返回
```

**安全要点**：
- SECRET_KEY 至少 256 bit 随机数，存环境变量
- access_token 短期（小时级），refresh_token 存 Redis 可撤销
- HTTPS 传输（明文token被截获=账号被盗）
- Payload 不放密码等敏感信息（Base64可解码）

---

### Q: 如何保证接口幂等性？（支付场景）

**答**：

场景：用户点击"支付"，网络波动，客户端重试了3次，不能扣款3次！

方案：**幂等Token（Idempotency Key）**

```
1. 客户端生成唯一 idempotency_key（UUID）
2. 请求头带上 Idempotency-Key: uuid-xxx
3. 服务器检查 Redis 中是否存在这个 key
   - 存在 → 直接返回之前的结果（不执行业务逻辑）
   - 不存在 → 执行业务，把结果存入 Redis（key=idempotency_key, TTL=24h）
4. 客户端重试时带同样的 key → 服务器返回缓存结果
```

```python
@router.post("/payment")
async def create_payment(
    request: PaymentRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    redis: Redis = Depends(get_redis)
):
    cache_key = f"idempotent:{idempotency_key}"
    
    # 检查是否已处理
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)  # 返回之前的结果
    
    # 处理业务（用分布式锁防并发重复）
    async with redis_lock(f"lock:{idempotency_key}"):
        # 双重检查
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        result = await process_payment(request)
        await redis.set(cache_key, json.dumps(result), ex=86400)
    
    return result
```

---

### Q: 什么是微服务？和单体架构相比有什么优缺点？

**答**：

**单体架构**：所有功能在一个进程中，ChipWise 的 FastAPI 就是单体（一个进程包含所有路由）。

**微服务架构**：每个功能拆成独立服务（独立部署、独立扩容）。

| 维度 | 单体 | 微服务 |
|------|------|--------|
| 部署 | 简单，一个进程 | 复杂，多个服务 |
| 扩容 | 整体扩，浪费 | 按需扩某个服务 |
| 技术栈 | 统一 | 每个服务可用不同语言 |
| 故障隔离 | 一处崩全崩 | 局部故障影响有限 |
| 调用延迟 | 函数调用（纳秒） | 网络调用（毫秒） |
| 数据一致性 | 事务简单 | 分布式事务复杂 |
| 适用 | 小团队、早期项目 | 大团队、高并发、复杂业务 |

**ChipWise 的折中**：应用层单体（FastAPI），但模型层微服务（BGE-M3、bce-reranker 独立部署）——这是务实的中间方案。

---

## 16.6 场景题

### Q: 10 亿条记录如何做分页？

**答**：

**普通翻页（OFFSET）的问题**：
```sql
SELECT * FROM records ORDER BY id LIMIT 20 OFFSET 999999980;
-- 数据库需要扫描9亿+行，然后丢掉，只返回最后20行！极慢！
```

**游标分页（Cursor-based）**，也称 Seek 方法：
```sql
-- 第一页
SELECT * FROM records ORDER BY id LIMIT 20;
-- 记住最后一行的 id = 20

-- 下一页（用id做游标）
SELECT * FROM records WHERE id > 20 ORDER BY id LIMIT 20;
-- 直接从索引定位id=20的位置，O(log n)！
```

游标分页的限制：
- 不能直接跳到第N页（只能前后翻）
- 如果有删除，游标可能失效（可用 updated_at 等稳定字段）
- 适合"下一页"场景（信息流、聊天记录）

---

### Q: 如何实现分布式锁？

**答**：

场景：多台服务器的 Celery Worker 同时要处理同一个文档，只能有一个处理。

**Redis 分布式锁（SET NX EX）**：

```python
import uuid

async def acquire_lock(
    redis: Redis, 
    resource: str, 
    ttl: int = 30
) -> str | None:
    """尝试获取锁，返回lock_value（用于释放）或None（获取失败）"""
    lock_key = f"lock:{resource}"
    lock_value = str(uuid.uuid4())   # 唯一值，防止误释放别人的锁
    
    # SET key value NX EX ttl
    # NX = Not Exists，key不存在才设置（原子操作）
    # EX = 过期时间（防止持有锁的进程崩溃后死锁）
    ok = await redis.set(lock_key, lock_value, ex=ttl, nx=True)
    return lock_value if ok else None

async def release_lock(redis: Redis, resource: str, lock_value: str) -> bool:
    """释放锁（Lua脚本保证原子性）"""
    lock_key = f"lock:{resource}"
    # 用Lua脚本：比较value再删除，防止删掉别人的锁
    script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """
    result = await redis.eval(script, 1, lock_key, lock_value)
    return bool(result)

# 使用
lock_value = await acquire_lock(redis, f"doc:{doc_id}")
if lock_value:
    try:
        await process_document(doc_id)
    finally:
        await release_lock(redis, f"doc:{doc_id}", lock_value)
else:
    # 获取锁失败，有别的Worker在处理
    pass
```

**Redlock 算法**（多个 Redis 节点的分布式锁，更可靠）：
向 N（奇数）个独立 Redis 节点申请锁，超过 N/2+1 个成功才算获取锁。

---

### Q: 如何设计消息队列来处理高峰流量？

**答**（削峰填谷）：

场景：白天 QPS 100，晚高峰 QPS 10000，服务器只能处理 1000 QPS。

```
用户请求（10000 QPS）
     ↓
消息队列（缓冲）
     ↓
消费者（1000 QPS 匀速处理）
```

**关键设计**：

1. **生产者**：请求进队列后立刻返回 201 Accepted
2. **消费者**：固定速率消费，控制下游压力
3. **死信队列（DLQ）**：失败任务放入死信队列，人工处理
4. **消息幂等**：消费者处理前检查是否已处理（用 Redis 标记）
5. **消息顺序**：同一用户的消息路由到同一分区（Kafka partition by user_id）

ChipWise 用的是 **Celery + Redis** 方案，适合小中型规模。大规模用 Kafka/RabbitMQ。

---

## 16.7 代码实战题

### Q: 用 Python 实现一个 LRU 缓存

```python
from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = OrderedDict()   # 有序字典，记录插入/访问顺序
    
    def get(self, key: int) -> int:
        if key not in self.cache:
            return -1
        # 访问时移到末尾（最近使用）
        self.cache.move_to_end(key)
        return self.cache[key]
    
    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)  # 删除最久未使用的（头部）

# 测试
cache = LRUCache(2)
cache.put(1, 1)   # cache: {1:1}
cache.put(2, 2)   # cache: {1:1, 2:2}
cache.get(1)      # 返回1，cache: {2:2, 1:1}（1移到末尾）
cache.put(3, 3)   # 超容量，删除最久未使用的2，cache:{1:1, 3:3}
cache.get(2)      # 返回-1（已被淘汰）
```

---

### Q: 实现一个线程安全的单例模式

```python
import threading

class LLMFactory:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:               # 双重检查锁定
                if cls._instance is None:  # 再次检查（防止并发初始化）
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.client = create_llm_client()

# Python 更 Pythonic 的方式：模块级变量天然是单例
# 模块只会被导入一次（import机制保证）
# src/libs/llm/factory.py
_instance: LLMFactory | None = None

def get_factory() -> LLMFactory:
    global _instance
    if _instance is None:
        _instance = LLMFactory()
    return _instance
```

---

### Q: 用 asyncio 实现并发爬虫（控制并发数）

```python
import asyncio
import httpx
from typing import List

async def fetch(client: httpx.AsyncClient, url: str, semaphore: asyncio.Semaphore) -> str:
    async with semaphore:   # 控制并发数
        try:
            response = await client.get(url, timeout=10)
            return response.text
        except Exception as e:
            return f"Error: {e}"

async def crawl(urls: List[str], max_concurrent: int = 10) -> List[str]:
    semaphore = asyncio.Semaphore(max_concurrent)
    async with httpx.AsyncClient() as client:
        tasks = [fetch(client, url, semaphore) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

# 测试
urls = [f"https://example.com/chip/{i}" for i in range(100)]
asyncio.run(crawl(urls, max_concurrent=10))
```

---

## 16.8 算法与数据结构（后端面试也考）

### Q: 手写快速排序

```python
def quicksort(arr: list) -> list:
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)

# 时间复杂度：平均O(n log n)，最坏O(n²)（全相同时）
# 空间复杂度：O(log n)（递归栈）
```

### Q: 二分查找

```python
def binary_search(arr: list, target: int) -> int:
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1

# 时间复杂度 O(log n)，空间复杂度 O(1)
```

---

## 16.9 项目相关问题（针对本项目的面试准备）

### Q: 介绍一下你做的这个 RAG 项目的架构？

建议答题框架（STAR：背景、任务、行动、结果）：

**背景**：半导体硬件团队需要查询海量芯片参数，传统检索效率低。

**架构**：7层架构
1. Gradio 前端（7860）
2. FastAPI 网关（8080）：JWT认证、限速、CORS
3. Agent Orchestrator：ReAct循环，最多5轮工具调用
4. 核心服务：QueryRewriter、ConversationManager、ResponseBuilder
5. 模型服务：LM Studio(35B主模型/1.7B路由)、BGE-M3嵌入、bce-reranker重排
6. 存储层：PostgreSQL(关系数据)、Milvus(向量)、Redis(缓存/会话)、Kùzu(知识图谱)
7. 离线处理：Celery任务链（PDF提取→向量化→存储）

**关键设计决策**：
- 混合检索（稠密+稀疏向量）提高召回率
- 语义缓存（余弦相似度>0.95命中）降低LLM调用成本
- 优雅降级（LLM不可用返回503而不是500）
- 所有请求注入TraceID，全链路可观测

---

### Q: 你们的系统如何保证高可用？

1. **组件级别**：
   - 非关键组件（LLM/Reranker/Graph）失败不阻断主流程
   - `/readiness` 区分 `healthy/degraded`，degraded 时仍可提供基础服务

2. **重试策略**：
   - Celery 任务：最多3次重试，指数退避（2/4/8秒）
   - HTTP 调用：httpx 重试机制
   
3. **连接池**：数据库和 Redis 使用连接池，避免连接耗尽

4. **限速保护**：防止突发流量打垮下游服务

5. **数据持久化**：Redis RDB+AOF，PostgreSQL WAL

---

### Q: 你们如何处理 LLM 幻觉问题？

1. **RAG（检索增强）**：答案基于检索到的真实文档，而不是纯模型生成
2. **引用验证**：ResponseBuilder 标注每个结论的来源文档
3. **置信度阈值**：检索相关度低时，返回"未找到相关信息"而非猜测
4. **知识图谱校验**：对可以结构化验证的参数（如电压范围），用 Kùzu 二次验证
5. **重排模型**：bce-reranker 确保送入 LLM 的文档确实相关

---

# 附录

## A. 推荐学习路线

```
第1阶段（2周）：基础
├── HTTP 协议（第2章）
├── Python 类型注解 + Pydantic（第4章）
└── FastAPI 基础路由（第5.1-5.5）

第2阶段（2周）：核心
├── PostgreSQL + SQLAlchemy（第6-7章）
├── Redis 基础用法（第8.1-8.3）
└── JWT 认证（第11.1-11.3）

第3阶段（2周）：进阶
├── asyncio 异步编程（第10章）
├── Docker 与 Compose（第12章）
└── Celery 任务队列（第13章）

第4阶段（1周）：面试冲刺
├── 刷遍第16章所有问题
├── 用 ChipWise 项目举例回答
└── LeetCode 中等题 20道
```

## B. 速查表

### HTTP 状态码速查

```
200 OK              → 成功
201 Created         → 创建成功
202 Accepted        → 异步任务已接受
204 No Content      → 成功但无返回体
400 Bad Request     → 参数错误
401 Unauthorized    → 未认证（没 Token）
403 Forbidden       → 无权限（有 Token 但权限不足）
404 Not Found       → 资源不存在
409 Conflict        → 冲突（重复创建）
422 Unprocessable   → Pydantic 校验失败
429 Too Many Reqs   → 限速
500 Internal Error  → 服务器代码报错
503 Unavailable     → 依赖服务不可用
```

### Redis 命令速查

```bash
SET key value EX 3600       # 设置带过期时间
GET key                     # 获取
DEL key                     # 删除
EXISTS key                  # 是否存在（1/0）
EXPIRE key 600              # 设置/更新过期时间
TTL key                     # 查剩余过期时间
INCR counter                # 原子自增
HSET hash field value       # Hash设置
HGET hash field             # Hash获取
LPUSH list item             # List左推入
RPOP list                   # List右弹出
ZADD zset score member      # ZSet添加
ZRANGEBYSCORE zset min max  # ZSet范围查询
KEYS pattern                # 匹配keys（生产不要用！用SCAN）
SCAN cursor MATCH pattern   # 安全迭代
FLUSHDB                     # 清空当前DB（危险！）
```

### Docker 命令速查

```bash
docker-compose up -d                    # 后台启动所有服务
docker-compose down                     # 停止并删除容器
docker-compose ps                       # 查看状态
docker-compose logs -f <service>        # 查看日志
docker-compose restart <service>        # 重启某服务
docker exec -it <container> bash        # 进入容器
docker stats                            # 资源监控
docker images                          # 查看本地镜像
docker pull postgres:15                 # 拉取镜像
docker build -t myapp:latest .          # 构建镜像
```

---

> **最后的话**：后端知识广但有规律——所有技术都是在解决"可靠、快速、安全地传递和存储数据"这个问题。理解了问题本质，所有框架和工具都只是工具。
>
> 用 ChipWise 这个真实项目练习，效果远胜刷抽象题目。加油！
```

