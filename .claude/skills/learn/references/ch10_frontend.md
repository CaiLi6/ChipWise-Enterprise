# Chapter 10: Frontend (前端层)

## Teaching Guide

### 1. Introduction

**Connect to Chapter 2**: "还记得 API Gateway 暴露了 REST 和 SSE 端点吗？今天我们看看谁在调用它们——前端。"

### 2. Key Concepts

#### Two Frontends

| | Gradio MVP | Vue3 Production |
|---|---|---|
| 目的 | 快速原型验证 | 生产级 UI |
| 技术栈 | Python Gradio | Vite + Vue3 + Element Plus + Pinia |
| 端口 | 7860 | dev: 5173, prod: nginx 代理 |
| 状态 | deprecated | active |

#### Vue3 App Architecture

```
frontend/web/
├── src/
│   ├── views/          ← 页面组件 (QueryView, CompareView, LoginView...)
│   ├── components/     ← 可复用组件
│   ├── stores/         ← Pinia 状态管理 (auth, query, layout)
│   ├── router/         ← Vue Router
│   ├── api/            ← HTTP client (axios)
│   └── App.vue         ← Root component
├── vite.config.ts
└── package.json
```

#### Key Patterns

- **SSE Streaming**: Query response streamed via `EventSource` to `/api/v1/query/stream`
- **JWT Token**: Stored in Pinia auth store, sent as `Authorization: Bearer` header
- **Element Plus**: Chinese-friendly UI component library (tables, forms, dialogs)

### 3. Code Walkthrough

**Files to read**:

1. `frontend/web/src/stores/` — Pinia stores (how state is managed)
2. `frontend/web/src/views/` — Page components
3. `frontend/gradio_app.py` — Gradio MVP (simple, good for understanding the API contract)

### 5. Quiz Questions

**Q1 (Concept)**: 为什么保留 deprecated 的 Gradio 而不删除？

**A1**: 1) Gradio 是快速 demo 工具——给客户或领导演示时，不需要编译前端，`python gradio_app.py` 即可; 2) 后端开发调试时不想启动 Vue 编译; 3) 代码量极少（一个文件），维护成本低。

**Q2 (Code reading)**: Vue3 的 query view 怎么处理 SSE streaming？每次收到一个 token 怎么更新界面？

**A2**: 使用 `EventSource` API 连接 `/api/v1/query/stream`，每次 `onmessage` 事件触发时将 token 追加到 Pinia store 中的 response 字段，Vue 的响应式系统自动更新 DOM。

**Q3 (Design)**: 如果要给 Vue3 app 添加"芯片对比"页面，需要创建哪些文件？

**A3**: 1) `src/views/CompareView.vue` — 页面组件; 2) `src/stores/compare.ts` — Pinia store (管理对比状态); 3) `src/router/` 添加路由; 4) `src/api/` 添加 compare API 调用。后端 `/api/v1/compare` 已就绪，前端只需对接。
