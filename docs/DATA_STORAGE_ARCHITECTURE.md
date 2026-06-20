# ChipWise Enterprise 数据存储架构

**文档版本**: 1.0  
**更新日期**: 2026-06-17

---

## 概述

ChipWise Enterprise 采用**多存储引擎协同架构**，根据数据特性选择最适合的存储方式：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           数据存储架构全景                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌────────────┐  │
│   │  PostgreSQL  │   │    Milvus    │   │    Redis     │   │    Kùzu    │  │
│   │    :5432     │   │    :19530    │   │    :6379     │   │  (嵌入式)   │  │
│   │              │   │              │   │              │   │            │  │
│   │  关系型数据   │   │  向量检索    │   │  缓存/队列   │   │  知识图谱   │  │
│   │  结构化存储   │   │  语义搜索    │   │  会话状态    │   │  关系推理   │  │
│   └──────────────┘   └──────────────┘   └──────────────┘   └────────────┘  │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                          文件系统                                     │  │
│   │   data/documents/  ← 原始 PDF        data/kuzu/  ← 图数据库文件       │  │
│   │   data/exports/    ← 导出报告        logs/       ← 日志追踪           │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. PostgreSQL — 关系型数据存储

**端口**: 5432  
**用途**: 结构化业务数据、元数据、审计日志

### 1.1 表结构

| 表名 | 用途 | 主要字段 |
|------|------|----------|
| `documents` | 文档元数据 | id, title, file_path, file_hash(SHA256), status, created_at |
| `chips` | 芯片主数据 | id, part_number, manufacturer, category, package, status |
| `chip_parameters` | 芯片参数 | id, chip_id, name, value, unit, category |
| `chip_alternatives` | 替代料关系 | chip_id, alternative_id, compatibility_level |
| `errata` | 勘误信息 | id, chip_id, errata_id, severity, description, workaround |
| `design_rules` | 设计规则 | id, chip_id, rule_type, content, source_page |
| `document_images` | 文档图片 | id, document_id, page_number, image_path, ocr_text |
| `bom_records` | BOM 记录 | id, user_id, name, created_at |
| `bom_items` | BOM 明细 | id, bom_id, part_number, quantity, notes |
| `knowledge_notes` | 团队知识库 | id, user_id, title, content, tags |
| `users` | 用户账号 | id, username, email, password_hash, role, sso_provider |
| `query_audit_log` | 查询审计 | id, user_id, query, response_summary, latency_ms, trace_id |
| `alembic_version` | 迁移版本 | version_num |

### 1.2 数据示例

```sql
-- 芯片数据
INSERT INTO chips (part_number, manufacturer, category)
VALUES ('STM32F407VGT6', 'STMicroelectronics', 'MCU');

-- 参数数据
INSERT INTO chip_parameters (chip_id, name, value, unit, category)
VALUES (1, 'Max Frequency', '168', 'MHz', 'Performance');
```

---

## 2. Milvus — 向量数据库

**端口**: 19530  
**用途**: 语义检索、相似度搜索

### 2.1 Collection 结构

| Collection | 用途 | 记录数 |
|------------|------|--------|
| `datasheet_chunks` | 文档分片向量 | ~数万条 |
| `knowledge_notes` | 知识库向量 | ~数百条 |

### 2.2 `datasheet_chunks` Schema

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INT64 (PK) | 主键 |
| `document_id` | VARCHAR | 关联 PostgreSQL documents.id |
| `chunk_index` | INT32 | 分片序号 |
| `content` | VARCHAR | 原始文本内容 |
| `dense_vector` | FloatVector(1024) | BGE-M3 稠密向量 |
| `sparse_vector` | SparseFloatVector | BGE-M3 稀疏向量 (词汇级) |
| `bm25_vector` | SparseFloatVector | Milvus BM25 自动生成 (可选) |
| `metadata` | JSON | page_number, section, chip_name 等 |

### 2.3 索引配置

```python
# 稠密向量索引 (HNSW)
index_params = {
    "metric_type": "COSINE",
    "index_type": "HNSW",
    "params": {"M": 16, "efConstruction": 256}
}
search_params = {"ef": 128}

# 稀疏向量索引 (Inverted Index)
sparse_index = {"index_type": "SPARSE_INVERTED_INDEX"}
```

### 2.4 检索方式

```python
# 混合检索 (Dense + Sparse + RRF)
results = collection.hybrid_search(
    reqs=[dense_req, sparse_req],
    rerank=RRFRanker(k=60),
    limit=30
)
```

---

## 3. Redis — 缓存与队列

**端口**: 6379  
**用途**: 会话状态、语义缓存、任务队列、限流

### 3.1 Key 命名空间

| Key Pattern | 用途 | TTL |
|-------------|------|-----|
| `session:{user_id}:{session_id}` | 对话历史 (最近 10 轮) | 1800s |
| `gptcache:query:{hash}` | 语义缓存 - 查询向量 | 3600-14400s |
| `gptcache:response:{hash}` | 语义缓存 - 响应内容 | 3600-14400s |
| `ratelimit:{user_id}:minute` | 用户分钟级限流计数 | 60s |
| `ratelimit:{user_id}:hour` | 用户小时级限流计数 | 3600s |
| `ratelimit:llm:semaphore` | LLM 全局并发信号量 | - |
| `sso:state:{state}` | SSO CSRF state | 600s |
| `task:progress:{task_id}` | Celery 任务进度 | 86400s |
| `chipwise_sessions_v1::{username}` | 前端会话历史 | 持久 |

### 3.2 数据库分配

| DB | 用途 |
|----|------|
| DB 0 | 应用缓存 + 会话 + 限流 |
| DB 1 | Celery Broker + Result Backend |

### 3.3 数据示例

```python
# 对话历史存储
redis.setex(
    f"session:{user_id}:{session_id}",
    1800,
    json.dumps({"turns": [...], "created_at": "..."})
)

# 语义缓存
redis.setex(f"gptcache:query:{hash}", 3600, query_vector.tobytes())
redis.setex(f"gptcache:response:{hash}", 3600, json.dumps(response))
```

---

## 4. Kùzu — 知识图谱

**部署方式**: 嵌入式 (进程内)  
**数据目录**: `data/kuzu/` (约 25 MB)  
**用途**: 芯片关系推理、多跳查询

### 4.1 Node Tables (6 种节点)

| 节点类型 | 属性 | 说明 |
|----------|------|------|
| `Chip` | name, manufacturer, package, status | 芯片主体 |
| `Parameter` | name, value, unit, category | 参数值 |
| `Errata` | errata_id, severity, description, workaround | 勘误信息 |
| `Document` | title, sha256, source_url, pages | 文档来源 |
| `DesignRule` | rule_type, content, chip_id | 设计规则 |
| `Peripheral` | name, type | 外设 (SPI/I2C/UART...) |

### 4.2 Edge Tables (7 种关系)

```
(Chip)──[:HAS_PARAM]──▶(Parameter)
(Chip)──[:HAS_ERRATA]──▶(Errata)
(Chip)──[:HAS_PERIPHERAL]──▶(Peripheral)
(Chip)──[:ALTERNATIVE_TO]──▶(Chip)        ← 替代料双向
(Chip)──[:HAS_DESIGN_RULE]──▶(DesignRule)
(Document)──[:DESCRIBES]──▶(Chip)
(Errata)──[:AFFECTS]──▶(Peripheral)
```

### 4.3 查询示例

```cypher
-- 查找芯片的所有参数
MATCH (c:Chip {name: 'STM32F407'})-[:HAS_PARAM]->(p:Parameter)
RETURN p.name, p.value, p.unit

-- 查找替代料及其勘误
MATCH (c:Chip {name: 'STM32F407'})-[:ALTERNATIVE_TO]->(alt:Chip)
OPTIONAL MATCH (alt)-[:HAS_ERRATA]->(e:Errata)
RETURN alt.name, e.errata_id, e.severity

-- 查找影响 SPI 的勘误
MATCH (e:Errata)-[:AFFECTS]->(p:Peripheral {name: 'SPI'})
RETURN e.errata_id, e.description
```

---

## 5. 文件系统

| 目录 | 用途 | 内容 |
|------|------|------|
| `data/documents/` | 原始文档 | 上传的 PDF/XLSX 文件 |
| `data/incoming/` | 待处理文档 | 爬虫下载的临时文件 |
| `data/exports/` | 导出文件 | 生成的报告 (PDF/XLSX) |
| `data/kuzu/` | 图数据库 | Kùzu 数据文件 |
| `data/golden_qa.jsonl` | 评估数据 | 黄金测试集 |
| `data/eval/` | 评估结果 | 评估运行输出 |
| `logs/` | 日志文件 | 应用日志、追踪日志 |
| `logs/traces.jsonl` | 追踪日志 | 全链路 trace 记录 |

---

## 6. 数据流 — 离线 Ingestion

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              离线 Ingestion 流程                            │
└─────────────────────────────────────────────────────────────────────────────┘

   PDF 文件                                                                    
       │                                                                       
       ▼                                                                       
   ┌───────────────┐                                                          
   │ 1. 文件存储   │ ──▶ data/documents/{doc_id}.pdf  [文件系统]              
   │    SHA256去重  │                                                          
   └───────┬───────┘                                                          
           │                                                                   
           ▼                                                                   
   ┌───────────────┐                                                          
   │ 2. 元数据写入 │ ──▶ PostgreSQL.documents (id, title, hash, status)       
   └───────┬───────┘                                                          
           │                                                                   
           ▼                                                                   
   ┌───────────────┐                                                          
   │ 3. PDF 解析   │     提取文本 + 表格 (pdfplumber/Camelot/PaddleOCR)       
   │    表格提取   │                                                          
   └───────┬───────┘                                                          
           │                                                                   
           ▼                                                                   
   ┌───────────────┐                                                          
   │ 4. LLM 抽取   │ ──▶ PostgreSQL.chips / chip_parameters / errata          
   │    结构化参数 │     (芯片名、参数、勘误、替代料)                          
   └───────┬───────┘                                                          
           │                                                                   
           ▼                                                                   
   ┌───────────────┐                                                          
   │ 5. 文本分片   │     1000 字符/片, 200 字符重叠                           
   │    Chunking   │     输出: List[Chunk]                                    
   └───────┬───────┘                                                          
           │                                                                   
           ▼                                                                   
   ┌───────────────┐                                                          
   │ 6. 向量化     │ ──▶ BGE-M3 生成 dense (1024d) + sparse 向量              
   │    Embedding  │                                                          
   └───────┬───────┘                                                          
           │                                                                   
           ├──────────────────────────────┐                                   
           ▼                              ▼                                   
   ┌───────────────┐              ┌───────────────┐                           
   │ 7a. Milvus    │              │ 7b. PostgreSQL│                           
   │    向量写入   │              │    文本写入   │                           
   │    (chunks)   │              │    (chunks)   │                           
   └───────┬───────┘              └───────┬───────┘                           
           │                              │                                   
           └──────────────┬───────────────┘                                   
                          ▼                                                   
                  ┌───────────────┐                                           
                  │ 8. Kùzu 同步  │ ──▶ 图节点 + 关系写入                     
                  │    知识图谱   │     (Chip → Parameter → Errata)           
                  └───────────────┘                                           
```

---

## 7. 数据流 — 在线 Query

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              在线 Query 流程                                │
└─────────────────────────────────────────────────────────────────────────────┘

   用户查询: "STM32F407 的 SPI 最大频率是多少?"                                
       │                                                                       
       ▼                                                                       
   ┌───────────────┐                                                          
   │ 1. 缓存检查   │ ◀── Redis gptcache:* (语义相似度 > 0.95 命中)            
   │    GPTCache   │                                                          
   └───────┬───────┘                                                          
           │ (Cache Miss)                                                     
           ▼                                                                   
   ┌───────────────┐                                                          
   │ 2. 会话加载   │ ◀── Redis session:{user}:{session} (历史 10 轮)          
   │    历史上下文 │                                                          
   └───────┬───────┘                                                          
           │                                                                   
           ▼                                                                   
   ┌───────────────┐                                                          
   │ 3. 查询改写   │ ◀── LLM Router (代词消解、实体识别)                      
   │    QueryRewrite│                                                         
   └───────┬───────┘                                                          
           │                                                                   
           ▼                                                                   
   ┌───────────────────────────────────────────────────────────┐              
   │ 4. Agent Orchestrator (ReAct Loop)                        │              
   │                                                           │              
   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │              
   │   │ Tool A      │  │ Tool B      │  │ Tool C      │      │              
   │   │ rag_search  │  │ graph_query │  │ sql_query   │      │              
   │   │     │       │  │     │       │  │     │       │      │              
   │   │     ▼       │  │     ▼       │  │     ▼       │      │              
   │   │  Milvus     │  │   Kùzu      │  │ PostgreSQL  │      │              
   │   │  向量检索   │  │  图查询     │  │  SQL查询    │      │              
   │   └─────────────┘  └─────────────┘  └─────────────┘      │              
   └───────────────────────────┬───────────────────────────────┘              
                               │                                              
                               ▼                                              
   ┌───────────────┐                                                          
   │ 5. 响应生成   │ ◀── LLM Primary (综合 Tool 结果生成回答)                 
   │    + 引用     │                                                          
   └───────┬───────┘                                                          
           │                                                                   
           ├──────────────────────────────┐                                   
           ▼                              ▼                                   
   ┌───────────────┐              ┌───────────────┐                           
   │ 6a. 缓存写入  │              │ 6b. 会话更新  │                           
   │ Redis gptcache│              │ Redis session │                           
   └───────────────┘              └───────┬───────┘                           
                                          │                                   
                                          ▼                                   
                                  ┌───────────────┐                           
                                  │ 6c. 审计日志  │                           
                                  │ PG query_log  │                           
                                  └───────────────┘                           
```

---

## 8. 存储容量参考

| 存储 | 数据类型 | 单条大小 | 预估容量 (1万文档) |
|------|----------|----------|-------------------|
| PostgreSQL | 文档元数据 | ~1 KB | ~10 MB |
| PostgreSQL | 芯片+参数 | ~5 KB/芯片 | ~50 MB |
| Milvus | 向量分片 | ~8 KB/chunk | ~8 GB (100万chunks) |
| Redis | 会话缓存 | ~10 KB/session | ~200 MB (20用户) |
| Kùzu | 图数据 | - | ~100 MB |
| 文件系统 | PDF 文档 | ~2 MB/文件 | ~20 GB |

---

## 总结

| 数据类型 | 存储位置 | 存储形式 | 访问方式 |
|----------|----------|----------|----------|
| 文档元数据 | PostgreSQL | 关系表 | SQL |
| 芯片/参数/勘误 | PostgreSQL | 关系表 | SQL |
| 用户/权限/审计 | PostgreSQL | 关系表 | SQL |
| 文本分片向量 | Milvus | 向量 Collection | gRPC API |
| 对话历史 | Redis | JSON String | Key-Value |
| 语义缓存 | Redis | Binary/JSON | Key-Value |
| 限流计数 | Redis | Counter | INCR/EXPIRE |
| 任务队列 | Redis | List/Stream | Celery |
| 知识图谱 | Kùzu (嵌入式) | 图结构 | openCypher |
| 原始文档 | 文件系统 | PDF/XLSX | 路径读取 |
| 日志/追踪 | 文件系统 | JSONL | 日志分析 |
