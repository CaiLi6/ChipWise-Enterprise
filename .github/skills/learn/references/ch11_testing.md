# Chapter 11: Testing Strategy (测试策略)

## Teaching Guide

### 1. Introduction

**Core question**: "怎么保证这么复杂的系统不会改一处坏一片？"

### 2. Key Concepts

#### Test Pyramid

```
        /\
       /  \     E2E tests (Playwright, full stack)
      /    \
     /------\   Integration tests (Docker services)
    /        \
   /----------\  Unit tests (no Docker, mocked dependencies)
  /____________\
```

#### 5 Test Markers

| Marker | Needs Docker | Needs LM Studio | Use Case |
|--------|-------------|-----------------|----------|
| `unit` | No | No | Pure logic, mocked deps |
| `integration` | Yes | Yes | Full stack |
| `integration_nollm` | Yes | No | PG + Milvus + Redis only |
| `e2e` | Yes | Yes | Browser + API |
| `load` | Yes | Yes | Locust load testing |

```bash
pytest -m unit                    # Fast, no Docker
pytest -m integration_nollm      # Infra only
pytest -m "not load"              # Everything except load
```

#### Key Testing Patterns

**1. dependency_overrides (FastAPI)**
```python
app.dependency_overrides[get_current_user] = lambda: UserInfo(...)
app.dependency_overrides[get_orchestrator] = lambda: mock_orch
```

**2. InMemoryVectorStore (Contract testing)**
```python
class InMemoryVectorStore(BaseVectorStore):
    # Implements all abstract methods with dict storage
    # Verifies the interface contract without Milvus
```

**3. asyncio_mode = "auto"**
No `@pytest.mark.asyncio` decorator needed — auto-detected.

### 3. Code Walkthrough

**Files to read**:

1. `tests/unit/test_milvus_store_contract.py` — Contract testing pattern
2. `tests/unit/test_hybrid_search.py` — AsyncMock-based unit test
3. `tests/unit/test_hybrid_search_bm25.py` — BM25-specific tests
4. `tests/unit/test_smoke_imports.py` — Fast import validation
5. `conftest.py` — Shared fixtures

### 5. Quiz Questions

**Q1 (Concept)**: "Contract test" 和 "integration test" 有什么区别？InMemoryVectorStore 测试了什么？

**A1**: Contract test 验证"接口契约"——InMemoryVectorStore 和 MilvusStore 都实现 BaseVectorStore，contract test 确保 InMemoryVectorStore 的行为符合接口规范（upsert 返回 count、query 返回 RetrievalResult 等）。Integration test 验证"真实集成"——连真实 Milvus 验证网络、序列化、索引行为。

**Q2 (Code reading)**: 在 `test_hybrid_search.py` 中，`mock_store = AsyncMock(spec=BaseVectorStore)`。`spec=BaseVectorStore` 的作用是什么？去掉会怎样？

**A2**: `spec=BaseVectorStore` 让 mock 只暴露 BaseVectorStore 定义的方法和属性。调用不存在的方法会报 AttributeError。去掉后 mock 会接受任何属性访问，可能隐藏拼写错误（比如误写 `hybrid_serach`）。

**Q3 (Design)**: 如果要测试 "BM25 模式下检索 STM32F407 能否命中正确文档"，这是哪种 marker？需要什么依赖？

**A3**: `integration_nollm` marker（需要 Milvus 但不需要 LM Studio）。依赖: Docker 中 Milvus 运行 + 已初始化 BM25 schema + 已入库测试数据。BGE-M3 也需要运行（提供 dense embedding）。如果 BGE-M3 也不可用，降级为 `integration` marker。
