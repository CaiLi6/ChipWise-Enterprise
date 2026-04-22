# Architecture Overview

> For a new team member to understand ChipWise Enterprise in 10 minutes.

## 1. Seven-Layer Architecture

```mermaid
graph TB
    subgraph "Layer 1 — Frontend"
        VUE["Vue3 + Element Plus<br/>(production)"]
        GRADIO["Gradio MVP<br/>(deprecated)"]
    end

    subgraph "Layer 2 — API Gateway"
        API["FastAPI :8080<br/>JWT · Rate Limit · CORS · Tracing"]
    end

    subgraph "Layer 3 — Agent Orchestrator"
        AGENT["ReAct Loop (max 5 iter)<br/>LLM selects tools dynamically"]
    end

    subgraph "Layer 4 — Core Services"
        QR["QueryRewriter"]
        CM["ConversationManager"]
        RB["ResponseBuilder"]
        RE["ReportEngine"]
    end

    subgraph "Layer 5 — Model Services"
        LM["LM Studio :1234<br/>Primary 35B + Router 1.7B"]
        EMB["BGE-M3 :8001<br/>Dense + Sparse"]
        RR["bce-reranker :8002"]
    end

    subgraph "Layer 6 — Storage"
        PG["PostgreSQL :5432"]
        MV["Milvus :19530"]
        RD["Redis :6379"]
        KZ["Kùzu (embedded)"]
    end

    subgraph "Layer 7 — Libs"
        LIB["Pluggable abstractions<br/>BaseLLM · BaseEmbedding<br/>BaseVectorStore · BaseReranker<br/>BaseGraphStore"]
    end

    VUE --> API
    GRADIO --> API
    API --> AGENT
    AGENT --> QR & CM & RB & RE
    QR & CM & RB & RE --> LIB
    LIB --> LM & EMB & RR
    LIB --> PG & MV & RD & KZ
```

## 2. Online Query Flow

```mermaid
sequenceDiagram
    participant U as User
    participant GW as API Gateway
    participant SC as SemanticCache
    participant CM as ConversationManager
    participant AO as AgentOrchestrator
    participant T as Tools
    participant RB as ResponseBuilder

    U->>GW: POST /api/v1/query
    GW->>GW: JWT verify + rate limit
    GW->>SC: cosine > 0.95?
    alt Cache hit
        SC-->>GW: cached answer
    else Cache miss
        GW->>CM: load conversation context
        CM->>AO: ProcessedQuery
        loop ReAct (max 5 iterations)
            AO->>AO: Thought
            AO->>T: Tool Calls (parallel)
            T-->>AO: Observations
        end
        AO->>RB: final answer + citations
        RB-->>GW: QueryResponse
        GW->>SC: store in cache
    end
    GW-->>U: JSON / SSE stream
```

## 3. Offline Ingestion Pipeline

```mermaid
flowchart LR
    DL["Download<br/>(URL/Upload)"] --> DD["SHA256<br/>Dedup"]
    DD --> PDF["PDF Extract<br/>(pdfplumber)"]
    PDF --> TBL["3-Tier Table<br/>Extract"]
    TBL --> PARAM["LLM Param<br/>Extract"]
    PARAM --> CHK["Chunking<br/>(5 strategies)"]
    CHK --> EMB["BGE-M3<br/>Embed"]
    EMB --> MV["Milvus<br/>Upsert"]
    EMB --> PG["PostgreSQL<br/>Upsert"]
    PG --> KZ["Kùzu Graph<br/>Sync"]

    style DL fill:#e1f5fe
    style MV fill:#c8e6c9
    style PG fill:#c8e6c9
    style KZ fill:#c8e6c9
```

Celery chains orchestrate the pipeline across 3 worker queues:
- **default/embedding** — main ingestion + embedding
- **heavy** — PaddleOCR (3 GB footprint, loaded on-demand)
- **crawler** — Playwright web scraping (rate-limited per domain)

## 4. Storage Topology

```mermaid
graph LR
    subgraph "PostgreSQL"
        PG_DOC["Documents metadata"]
        PG_CHIP["Chip parameters"]
        PG_USER["Users + auth"]
        PG_ERRATA["Errata records"]
    end

    subgraph "Milvus"
        MV_DENSE["Dense vectors<br/>1024-dim HNSW"]
        MV_SPARSE["Sparse vectors<br/>BM25-like"]
        MV_HYBRID["Hybrid search<br/>RRF k=60"]
    end

    subgraph "Redis"
        RD_SESS["Sessions (DB 0)"]
        RD_CACHE["Semantic Cache (DB 0)"]
        RD_RATE["Rate Limits (DB 0)"]
        RD_CELERY["Celery Broker (DB 1)"]
    end

    subgraph "Kùzu (embedded)"
        KZ_GRAPH["6 node tables<br/>7 edge tables<br/>openCypher queries"]
    end
```

## 5. Key Design Decisions

### Why LM Studio?
All inference runs on a single AMD Ryzen AI 395 machine (128 GB RAM). LM Studio provides an OpenAI-compatible API for local model serving with zero data exfiltration — critical for semiconductor IP protection. The dual-model setup (35B primary + 1.7B router) balances quality with latency.

### Why Milvus Hybrid Search?
BGE-M3 produces both dense (semantic) and sparse (lexical) vectors in a single call. Milvus's native `hybrid_search()` with RRF fusion (k=60) combines semantic understanding with exact keyword matching — essential for chip part numbers like "STM32F407VGT6" that pure semantic search would miss.

### Why Kùzu Embedded?
Chip relationships (parameter inheritance, errata links, peripheral compatibility) are naturally a graph. Kùzu runs embedded in-process — no extra service to deploy or manage. openCypher queries enable multi-hop traversals that would require complex SQL JOINs. Synced from PostgreSQL after each ingestion.

### Why Celery with 3 Queues?
Different ingestion tasks have vastly different resource profiles: PaddleOCR needs 3 GB RAM (heavy queue), Playwright is I/O-bound with rate limits (crawler queue), embedding is GPU/CPU-bound (default queue). Separate queues with `worker_prefetch_multiplier=1` prevent one slow task from blocking others. `task_acks_late=True` ensures reliability on worker crashes.
