<div align="center">

# CampusMind AI

<a href="https://git.io/typing-svg">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=700&size=28&duration=2800&pause=1100&color=2563EB&multiline=false&center=true&vCenter=true&repeat=true&width=740&height=50&lines=CampusMind+AI;Intelligent+University+Knowledge+Assistant;RAG+%E2%80%A2+Hybrid+Search+%E2%80%A2+Semantic+Caching;Powered+by+AI" alt="CampusMind AI - Intelligent University Knowledge Assistant - RAG • Hybrid Search • Semantic Caching - Powered by AI" />
</a>

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=1,2,3,4&bg_color=2563eb,7c3aed,06b6d4&height=4&section=header" alt="Gradient Border" width="740" />
</p>

<p align="center">
  <strong>Production-ready university knowledge assistant delivering verifiable, grounded answers from institutional documents using Hybrid RAG (Qdrant + BM25 + RRF + BGE Cross-Encoder Reranker), Groq LLM inference, and high-performance Redis answer caching.</strong>
</p>

<p align="center">
  <a href="#table-of-contents">Documentation</a> •
  <a href="#caching-reading-assignment">Caching Reading Assignment</a> •
  <a href="#system-architecture-and-rag-workflow">Architecture</a> •
  <a href="#api-endpoints">API Routes</a> •
  <a href="#installation-and-setup-instructions">Setup Guide</a>
</p>

<!-- Technology Badges -->
<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/React_18-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React 18" />
  <img src="https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white" alt="Vite" />
  <img src="https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white" alt="Tailwind CSS" />
  <img src="https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white" alt="Redis" />
  <img src="https://img.shields.io/badge/Qdrant-DC2626?style=for-the-badge&logo=qdrant&logoColor=white" alt="Qdrant" />
  <img src="https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white" alt="MySQL" />
  <img src="https://img.shields.io/badge/Groq_Cloud-F55036?style=for-the-badge&logo=groq&logoColor=white" alt="Groq" />
  <img src="https://img.shields.io/badge/Tests-122_Passing-22C55E?style=for-the-badge&logo=pytest&logoColor=white" alt="Pytest" />
</p>

</div>

---

## Table of Contents

- [1. Caching Reading Assignment](#caching-reading-assignment)
  - [A. Cache-aside vs Read-through](#a-cache-aside-vs-read-through)
  - [B. Write-through vs Write-behind / Write-back vs Write-around](#b-write-through-vs-write-behind--write-back-vs-write-around)
  - [C. TTL vs Cache Invalidation vs Eviction](#c-ttl-vs-cache-invalidation-vs-eviction)
  - [D. LRU vs LFU vs FIFO vs Random](#d-lru-vs-lfu-vs-fifo-vs-random)
  - [E. Redis-Supported Eviction Policies](#e-redis-supported-eviction-policies)
  - [F. Trade-offs and Justification of CampusMind AI Choices](#f-trade-offs-and-justification-of-campusmind-ai-choices)
- [2. Project Overview and Key Features](#project-overview-and-key-features)
- [3. System Architecture and RAG Workflow](#system-architecture-and-rag-workflow)
- [4. Redis Caching Architecture and Implementation](#redis-caching-architecture-and-implementation)
- [5. Semantic Caching Architecture and Implementation](#semantic-caching-architecture-and-implementation)
- [6. Technology Stack](#technology-stack)
- [7. Project Structure](#project-structure)
- [8. Installation and Setup Instructions](#installation-and-setup-instructions)
- [9. Environment Configuration](#environment-configuration)
- [10. Running the Application](#running-the-application)
- [11. API Endpoints](#api-endpoints)
- [12. Testing and Evaluation](#testing-and-evaluation)
- [13. Design Decisions and Trade-offs](#design-decisions-and-trade-offs)
- [14. Limitations and Future Improvements](#limitations-and-future-improvements)
- [15. Conclusion](#conclusion)

---

## Caching Reading Assignment

### A. Cache-aside vs Read-through

Caching read strategies dictate whether the application orchestrates cache lookups directly or delegates retrieval to an intermediary cache abstraction layer.

- **Cache-Aside (Lazy Loading)**: The application code directly queries the cache before contacting the underlying data source. If the key exists (cache hit), the cached value is returned directly. If the key is absent (cache miss), the application queries the database or performs expensive computations, populates the cache with the newly calculated result, and returns the response to the client. The cache has no knowledge of the backing store.
- **Read-Through**: The application interacts exclusively with the cache layer as if it were the primary database. On a cache miss, the cache infrastructure itself transparently intercepts the missing read, retrieves data from the backend store, populates itself, and delivers the payload to the calling application.

| Feature / Dimension | Cache-Aside (Lazy Loading) | Read-Through |
| :--- | :--- | :--- |
| **Data Retrieval Flow** | App checks Cache &rarr; on miss, App queries Database &rarr; App writes to Cache | App queries Cache &rarr; on miss, Cache fetches from Database transparently |
| **Missing Data Loader** | Application service layer | Cache provider / plugin / proxy |
| **Data Model Flexibility** | Highly flexible; cached shape can differ from database record (e.g., pre-rendered JSON, synthesized summaries) | Strict; cached object model matches database entity schema |
| **Failure Blast Radius** | High resilience; if cache fails, application falls back to direct database execution | Low resilience; if cache proxy is down, all reads can be blocked |
| **Cache Warming** | Lazy by nature; entries are cached only when requested (unless explicitly pre-warmed) | Lazy on access through provider plugin |
| **Appropriate Scenarios** | Heavy, heterogeneous computations, RAG inference, multi-source aggregations | Standard CRUD applications with strict 1:1 relational mappings |

> **CampusMind AI Architectural Choice**:  
> CampusMind AI utilizes **Cache-Aside**. The FastAPI service layer queries Redis using a deterministic question key. On a cache miss, the system executes the multi-stage RAG pipeline (embedding calculation, BM25 keyword retrieval, Qdrant dense vector search, Reciprocal Rank Fusion, Cross-Encoder reranking, and Groq LLM generation). Upon confirming sufficient grounding context, the application formats the serialized answer and populates Redis. If Redis is unavailable or times out, the application executes graceful fail-soft degradation without throwing fatal exceptions.

---

### B. Write-through vs Write-behind / Write-back vs Write-around

Write strategies govern synchronization between the cache and persistent storage when mutating state.

- **Write-Through**: Data is simultaneously written to the cache and the permanent database within a single transactional boundary before acknowledging completion to the client. Ensures strong consistency and low read latencies on subsequent calls, at the cost of higher write latency.
- **Write-Behind (Write-Back)**: Data is written directly to the cache, which acknowledges the client immediately. The cache layer asynchronously batches or queues writes to the persistent database at a later time. Offers the lowest write latency and absorbs burst traffic, but risks data loss if the cache instance crashes before flushing dirty pages.
- **Write-Around**: Writes bypass the cache entirely and are committed directly to persistent storage. Cache records are only created when data is subsequently read via cache-aside. Avoids cache churn for write-heavy data that is infrequently read, but initial reads following a write will invariably encounter cache misses.

| Feature / Dimension | Write-Through | Write-Behind / Write-Back | Write-Around |
| :--- | :--- | :--- | :--- |
| **Write Target** | Cache + DB synchronously | Cache synchronously, DB asynchronously | Database only (bypasses cache) |
| **Write Latency** | High (sum of cache and DB latency) | Very low (in-memory write only) | Standard database write latency |
| **Data Consistency** | High (cache and DB stay synchronized) | Eventual consistency; temporary window of divergence | High for DB; cache may hold stale data if not invalidated |
| **Data Loss Risk** | None; DB is committed before acknowledgment | High if cache crashes before dirty writes flush | None |
| **Ideal Workloads** | Critical transaction records, user authentication profiles | High-frequency telemetry, log buffering, live clickstream analytics | Archival writes, bulk document ingestion, batch administrative imports |

> **CampusMind AI Write Separation**:  
> Read operations in CampusMind AI operate via cache-aside, whereas administrative writes (document ingestion, MySQL chunk persistence, and vector indexing) follow a **Write-Around** model. Ingestion pipelines commit chunks to MySQL and vectors to Qdrant without writing synthesized answers into Redis. Synthetic answers are generated and cached on-demand when student questions are posed.

---

### C. TTL vs Cache Invalidation vs Eviction

Managing cache lifetime requires distinguishing temporal decay, manual invalidation, and memory reclamation:

1. **TTL (Time-To-Live)**:
   - **Mechanism**: A fixed duration assigned to a key upon creation. Redis automatically purges or expires keys when their time expires via passive checks on access and active periodic sampling.
   - **Role**: Establishes an absolute temporal ceiling on stale data, guaranteeing that cache drift eventually self-heals.
   - **Limitation**: TTL has zero awareness of underlying data mutations. If an administrative policy document changes 5 seconds after an answer is cached with a 30-minute TTL, the cache will continue returning outdated answers for 29 minutes and 55 seconds unless explicitly invalidated.
2. **Cache Invalidation**:
   - **Mechanism**: The deliberate revocation or blacklisting of cached data triggered by an event (e.g., document update, deletion, or re-indexing).
   - **Role**: Guarantees semantic freshness when source data changes.
   - **CampusMind AI Approach**: CampusMind AI employs **Knowledge-Base Versioning** (`DEFAULT_KB_VERSION="v1"`). Changing the active knowledge-base version immediately shifts the deterministic cache-key namespace. Older cache entries are instantly stranded and ignored, guaranteeing zero stale answer leakage without triggering expensive blocking `KEYS *` database sweeps.
3. **Eviction**:
   - **Mechanism**: The proactive removal of active, unexpired keys triggered strictly by resource constraints when Redis memory consumption reaches the configured `maxmemory` threshold.
   - **Role**: Protects Redis stability, preventing out-of-memory crashes (`OOM command not allowed`).
   - **CampusMind AI Approach**: CampusMind AI configures a deterministic memory limit (`maxmemory 100mb`) with configurable LRU/LFU memory policies (`allkeys-lru` / `allkeys-lfu`).

---

### D. LRU vs LFU vs FIFO vs Random

Eviction policies define key selection criteria when memory pressure mandates key reclamation:

| Algorithm | Full Name | Eviction Criterion | Advantages | Disadvantages | Ideal Workload |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **LRU** | Least Recently Used | Evicts keys whose last access timestamp (`idletime`) is the oldest. | Adapts rapidly to shifting temporal patterns and trending queries. | Susceptible to cache pollution during one-off full-table scans. | Conversational assistants, seasonal admissions, trending campus announcements. |
| **LFU** | Least Frequently Used | Evicts keys with the lowest logarithmic access counter (`freq`). | Retains core popular queries indefinitely even if temporarily unread. | Slow to de-prioritize historically popular items that fall out of favor (counter decay needed). | Fixed core curriculum guidelines, recurring semester degree criteria, static institutional policies. |
| **FIFO** | First In, First Out | Evicts keys strictly based on insertion timestamp, ignoring usage. | Minimal computational overhead; simple queue-like behavior. | Highly inefficient; frequently used hot keys are evicted simply because they are old. | Stream ingestion, time-series logging, ephemeral verification tokens. |
| **Random** | Random Eviction | Picks arbitrary candidate keys and purges them regardless of recency or frequency. | Near-zero CPU overhead; requires no access metadata tracking. | Poor cache hit rate; high risk of evicting mission-critical hot keys. | Uniform access distributions where tracking access statistics adds unnecessary overhead. |

> **Recency vs. Frequency**:  
> - **Recency (LRU)** prioritizes *when* a key was last touched. If an inquiry occurred 2 seconds ago, it is deemed hot; if it was touched 2 days ago, it is a prime candidate for eviction.  
> - **Frequency (LFU)** prioritizes *how often* a key has been accessed over its lifetime using a 24-bit logarithmic counter. A key requested 500 times remains protected against eviction even if it was not requested in the last hour, whereas a key requested only once is immediately eligible for removal.

---

### E. Redis-Supported Eviction Policies

Redis evaluates `maxmemory` limits and enforces one active eviction policy at runtime:

| Policy | Scope | Eviction Behavior |
| :--- | :--- | :--- |
| `noeviction` | All Keys | Returns an out-of-memory error on write commands that consume additional memory; read and delete commands succeed. |
| `allkeys-lru` | All Keys | Approximates Least Recently Used algorithm across the entire key space by sampling candidate keys. |
| `allkeys-lfu` | All Keys | Approximates Least Frequently Used algorithm using Morris 8-bit logarithmic counters across all keys. |
| `allkeys-random` | All Keys | Evicts randomly selected keys from the entire key space. |
| `volatile-lru` | Expiring Keys | Evicts least recently used keys among those with an explicit TTL (`expire`) set. |
| `volatile-lfu` | Expiring Keys | Evicts least frequently used keys among those with an explicit TTL (`expire`) set. |
| `volatile-random` | Expiring Keys | Randomly evicts keys among those with an explicit TTL (`expire`) set. |
| `volatile-ttl` | Expiring Keys | Evicts keys with the shortest remaining Time-To-Live (nearest to expiry). |

> [!IMPORTANT]
> **Redis Implementation Realities**:
> 1. **No Standard Native FIFO**: Redis does not provide an `allkeys-fifo` configuration directive. FIFO queue semantics must be implemented at the application tier using Redis `LIST` (`LPUSH`/`RPOP`) or `ZSET` structures with insertion epoch timestamps.
> 2. **Single Active Policy**: Redis enforces exactly one eviction policy at any given moment. LRU and LFU cannot run concurrently across the same Redis instance.
> 3. **Approximate Sampling**: Redis does not maintain an exact linked list of all items due to prohibitive memory overhead. Instead, it inspects an approximate sample of keys (configured via `maxmemory-samples`, default 5, tuned to 10 for higher precision in CampusMind AI) and evicts the best candidate among the sampled set.

---

### F. Trade-offs and Justification of CampusMind AI Choices

| Architectural Concept | CampusMind AI Implementation | Engineering Justification |
| :--- | :--- | :--- |
| **In-Memory Store** | Redis Standalone (`localhost:6379`) | Sub-millisecond latency (avg 0.5 ms hit latency), native key-level TTL, built-in memory eviction controls, and production durability. |
| **Caching Pattern** | Cache-Aside (Lazy Population) | The application controls RAG execution, evaluates answer grounding before caching, and gracefully recovers from cache outages without failure. |
| **Cache Key Construction** | SHA-256 Hash of Normalized Query | Query string trimming, lowercasing, and whitespace collapsing produce a fixed 64-character hash that prevents cache collisions and key bloating. |
| **Access Scope Segregation** | Included in Hash (`public` vs `all`) | Prevents role privilege leakage. Public student inquiries cannot read cached answers derived from restricted staff or administrative documents. |
| **Logical Cache Invalidation** | Knowledge-Base Version Prefix (`v1`) | Updates invalidate all cached RAG answers atomically without issuing blocking `KEYS *` or `FLUSHDB` commands. |
| **Temporal Expiration** | 30-Minute Default TTL (`1800s`) | Balances cache hit efficiency with institutional policy freshness while bounding memory consumption. |
| **Memory Eviction Strategy** | Configurable `allkeys-lru` / `allkeys-lfu` | Prevents Redis OOM crashes under high load. Administrators can toggle between recency and frequency models from the analytics UI. |
| **Grounded-Answer Guard** | `has_sufficient_context` Filtering | "I do not have sufficient information" responses and low-confidence outputs are rejected and never cached. |
| **Resilience & Fault Tolerance** | Non-blocking Fail-Soft Degradation | A Redis network failure, timeout, or crash logs a warning and falls back to live RAG generation without interrupting user sessions. |

---

## Project Overview and Key Features

CampusMind AI is an enterprise-grade academic knowledge platform designed to provide university students, faculty, and administrative staff with verified, citation-backed answers derived directly from official institutional documentation.

### Core Capabilities
- **Multi-Format Ingestion**: Ingests unstructured academic regulations, faculty handbooks, course syllabi, and administrative policies across PDF (`.pdf`), Microsoft Word (`.docx`), and Plain Text (`.txt`).
- **Configurable Chunking Pipeline**: Supports Fixed-Size (500 tokens), Recursive Structural Chunking (via LangChain), and Semantic Similarity-based chunking with metadata preservation (file name, page number, chunk ID).
- **Hybrid Vector + Keyword Search**: Dense cosine vector embeddings (`BAAI/bge-small-en-v1.5`, 384 dimensions) indexed in Qdrant combined with sparse lexical indexing via BM25Okapi.
- **Reciprocal Rank Fusion (RRF)**: Merges hybrid search candidates using $RRF(d) = \sum \frac{1}{60 + r(d)}$ to achieve robust precision and recall across keyword and conceptual queries.
- **Cross-Encoder Reranking (`BAAI/bge-reranker-base`)**: Post-RRF cross-attention neural reranking that scores full query-chunk pairs, discarding low-relevance candidates and returning the Top-K most relevant chunks to the LLM.
- **Strictly Grounded LLM Inference**: Groq-hosted open LLM generation (`openai/gpt-oss-120b`) constrained by system prompts that require direct inline citations (`[1]`, `[2]`) and reject ungrounded hallucinations.
- **Interactive Citation Inspector**: Frontend message cards provide structured citation chips displaying exact document source titles, chunk coordinates, and contextual text excerpts.
- **High-Performance Multi-Tier Caching**: Two-tier caching combining exact SHA-256 Redis lookups (~0.5 ms) and vector-based semantic caching via Qdrant (`campusmind_semantic_cache`, default cosine threshold 0.90) to serve paraphrased questions without redundant LLM generation.
- **Role-Based Access Control & Long-Lived Sessions**: Role enforcement across `student`, `staff`, and `admin` with secure JWT access tokens and database-backed refresh tokens for continuous session persistence.

---

## System Architecture and RAG Workflow

CampusMind AI integrates asynchronous FastAPI microservices with a responsive React frontend, managed Redis cache, Qdrant vector database, and MySQL relational store.

### End-to-End Ingestion and Retrieval Pipeline

```mermaid
flowchart TD
    subgraph Ingestion["1. Document Ingestion Pipeline"]
        A["Admin Uploads Document (.pdf, .docx, .txt)"] --> B["Document Extractor (PyMuPDF / python-docx)"]
        B --> C["Chunking Service (Recursive / Fixed / Semantic)"]
        C --> D["Embedding Service (BAAI/bge-small-en-v1.5 384d)"]
        D --> E[("Qdrant Vector Store (HNSW Index)")]
        C --> F["BM25 Indexer (Okapi Corpus)"]
        B --> G[("MySQL Database (Metadata & Persistence)")]
    end

    subgraph Retrieval["2. Hybrid Retrieval & Re-ranking"]
        H["User Query"] --> I["Parallel Retrieval"]
        I -->|"Dense Vector Search"| E
        I -->|"Sparse Lexical Search"| F
        E --> J["Qdrant Top-K Candidates"]
        F --> K["BM25 Top-K Candidates"]
        J --> L["Reciprocal Rank Fusion (RRF)"]
        K --> L
        L --> RR["Cross-Encoder Reranker (BAAI/bge-reranker-base)"]
        RR --> M["Top Scored Grounded Chunks"]
    end

    subgraph Synthesis["3. Grounded Synthesis"]
        M --> N["Groq LLM Provider (openai/gpt-oss-120b)"]
        H --> N
        N --> O["Grounded Answer with Source Citations [1]"]
    end
```

---

## Redis Caching Architecture and Implementation

CampusMind AI incorporates a low-latency Redis caching engine operating under the Cache-Aside pattern.

### Query Cache Decision Flow

```mermaid
flowchart TD
    Q["Student / Staff Asks Question"] --> N["Normalize Question (Lowercase & Trim Whitespace)"]
    N --> K["Generate Deterministic SHA-256 Key: (prefix + scope + version + hash)"]
    K --> R{"Check Redis Cache"}
    
    R -->|"Cache Hit"| H["Retrieve Serialized JSON Payload"]
    H --> D["Deserialize GroundedAnswer & Source Citations"]
    D --> B["Return Instant Answer (Sub-millisecond ~0.5ms) [Cached Badge]"]
    
    R -->|"Cache Miss"| E["Generate Query Embedding (BAAI/bge-small-en-v1.5 384d)"]
    E --> SC{"Check Qdrant Semantic Cache\n(campusmind_semantic_cache, cosine >= 0.90)"}
    
    SC -->|"Semantic Hit"| SH["Retrieve Redis Key from Top Qualifying Match"]
    SH --> RK{"Key Present in Redis?"}
    RK -->|"Yes"| D
    RK -->|"No (Expired/Evicted)"| HR["Fallback: Execute Hybrid RAG Pipeline"]
    
    SC -->|"Semantic Miss"| HR
    R -->|"Redis Unavailable / Timeout"| F["Fail-Soft Fallback: Log Warning & Bypass Cache"]
    F --> HR
    
    HR --> M["Execute Pipeline (Reuse Embedding + BM25 + RRF + BGE Reranker + Groq LLM)"]
    
    M --> C{"Has Sufficient Context & Grounded?"}
    C -->|"Yes"| S["Store Answer in Redis (TTL: 1800s)\n& Store Vector + Key in Semantic Cache"]
    C -->|"No (Not Found / Low Confidence)"| NO["Do Not Cache (Bypass Storing Stale Negatives)"]
    S --> RET["Return Generated Response to User"]
    NO --> RET
```

### Deterministic Cache Key Specification
Cache keys are constructed using SHA-256 hashes with four isolated dimensions:

$$\text{Key} = \text{namespace} : \text{scope} : \text{kb\_version} : \text{SHA256}(\text{normalized\_query})$$

- **Namespace**: `campusmind:answer` (isolates answer caching from session and rate-limit keys).
- **Access Scope**: `public` (accessible to students) or `all` (staff and administrators).
- **Knowledge-Base Version**: Defaults to `v1`. Re-indexing updates the version string, logically invalidating previous answers without blocking database commands.
- **Normalized Query**: Lowercased, stripped of leading/trailing whitespace, and collapsed of redundant internal whitespace before computing the SHA-256 digest.

---

## Semantic Caching Architecture and Implementation

### Why Semantic Caching Is Needed
Exact string-based Redis caching relies on SHA-256 digests of normalized query strings. While effective for identical or whitespace-normalized questions, it cannot recognize queries that convey identical intent with different wording (e.g., *"When is the library open?"* vs. *"What are the operating hours of the library?"*). 

Without semantic caching, each paraphrased question triggers redundant vector retrieval, BM25 scoring, cross-encoder reranking, and expensive LLM inference. Semantic caching bridges this gap by mapping query meaning into dense vector space, allowing semantically equivalent questions to reuse existing grounded answers.

### Architectural Separation: Qdrant vs. Redis
To maintain high performance and separation of concerns:
- **Qdrant Vector Database (`campusmind_semantic_cache`)**: Stores 384-dimensional query embeddings, deterministic Redis cache keys (`cache_key`), the original question string, `scope`, and `kb_version`. **Qdrant does NOT store the actual answer payload or source citations.**
- **Redis In-Memory Cache**: Acts as the single source of truth for the serialized `GroundedAnswer` objects (including answers, token usage, and structured source citations). Redis manages expiration TTLs and memory eviction (LRU/LFU).

### End-to-End Semantic Cache Flow

```
Incoming User Query
         │
         ▼
1. Exact Redis Cache Lookup (SHA-256)
   ├── Hit ──► Return GroundedAnswer immediately (~0.5 ms)
   └── Miss ──►
2. Generate Query Embedding via BGE-small (384 dimensions)
         │
         ▼
3. Qdrant Semantic Cache Search (`campusmind_semantic_cache`)
   - Payload Filters: `scope` == user_scope AND `kb_version` == current_version
   - Cosine Similarity Threshold: `score >= SEMANTIC_CACHE_THRESHOLD` (default: 0.90)
   - Candidate Selection: Qdrant retrieves the top qualifying candidate (`limit=1`)
         │
         ├── Match Found ──► Retrieve Answer from Redis using stored `cache_key`
         │                     ├── Key Active in Redis ──► Return GroundedAnswer (Semantic Cache Hit)
         │                     └── Key Expired or Evicted ──► Fall through to RAG Pipeline
         │
         └── No Match / Below Threshold ──► Fall through to RAG Pipeline
                                                   │
                                                   ▼
4. Full RAG Pipeline Fallback
   - Step A: Hybrid Retrieval (BM25 + Qdrant `campusmind_chunks`)
     * Reuses the query embedding from Step 2 (zero duplicate embedding overhead)
   - Step B: Reciprocal Rank Fusion (RRF)
   - Step C: Cross-Encoder Reranking (`BAAI/bge-reranker-base`)
   - Step D: Grounded LLM Generation (Groq `openai/gpt-oss-120b`)
                                                   │
                                                   ▼
5. Dual Cache Population (Grounded Answers Only)
   - If `has_sufficient_context` is True and `sources` are present:
     * Store GroundedAnswer in Redis with TTL (default 1800s)
     * Upsert (query_vector, cache_key, scope, kb_version) into `campusmind_semantic_cache`
   - If answer is ungrounded / low confidence: Do not cache in Redis or Qdrant
```

### Dedicated Collection Specification
- **Collection Name**: `campusmind_semantic_cache` (independent from the document chunk collection `campusmind_chunks`).
- **Vector Dimension**: 384 (matches `BAAI/bge-small-en-v1.5`).
- **Distance Metric**: Cosine distance (`rest.Distance.COSINE`). Because embeddings are L2 unit-normalized, the cosine similarity is the inner dot product:
  $$\text{Cosine Similarity}(\mathbf{u}, \mathbf{v}) = \sum_{i=1}^{384} u_i v_i$$
- **Access Scope & Version Isolation**: Queries are filtered strictly by `scope` (`public` vs `all`) and `kb_version` (`v1`). A student query cannot match a staff-cached question, and updating the knowledge-base version immediately invalidates previous semantic matches without requiring collection wipes.

### Candidate Selection & Threshold Filtering
- **Threshold**: Configured via `SEMANTIC_CACHE_THRESHOLD` (default: `0.90`).
- **Engine-Level Filtering**: Filtering is applied directly inside Qdrant via `score_threshold=min_score`, evaluating as $\text{score} \ge \text{threshold}$. Candidates below the threshold are rejected by Qdrant before reaching Python.
- **Top Match Selection**: In the current implementation, `SemanticCacheService.search_similar()` requests `limit=1` to select the single highest-scoring qualifying match.

### Expired or Evicted Redis Entries
If a question matches in Qdrant with high cosine similarity (e.g. `0.94`), but its corresponding Redis key has expired (past TTL) or was evicted by Redis memory pressure (`allkeys-lru`/`allkeys-lfu`), `cache_service.get_answer_by_key()` returns `None`. The orchestrator logs the expired entry and seamlessly falls through to the full RAG pipeline, generating a fresh grounded answer and re-populating both Redis and Qdrant.

---

## Technology Stack

### Backend Infrastructure
- **Framework**: FastAPI `0.115.6` with Uvicorn `0.32.1` ASGI server.
- **Language**: Python `3.12+` (type annotations, Pydantic v2 schemas).
- **Relational Storage**: MySQL `8.0` with SQLAlchemy `2.0+` ORM and PyMySQL driver.
- **In-Memory Cache**: Redis `8.1.0` client connecting to Redis Server `7.x`.
- **Vector Database**: Qdrant Client `1.20.0` (HNSW indexing, Cosine similarity).
- **Embeddings**: HuggingFace `sentence-transformers` (`BAAI/bge-small-en-v1.5`, 384 dimensions).
- **Cross-Encoder Reranker**: `sentence-transformers` CrossEncoder (`BAAI/bge-reranker-base`).
- **Text Extraction**: PyMuPDF `1.25.3` (PDF) and `python-docx` `1.1.2` (Word).
- **Lexical Search**: `rank-bm25` `0.2.2` (BM25Okapi ranking).
- **LLM Engine**: Groq Cloud SDK `1.7.0` running `openai/gpt-oss-120b`.
- **Security**: PyJWT `2.x` and Passlib/Bcrypt password hashing.

### Frontend Client
- **Framework**: React `18.3.1` with Vite `8.3.x` build toolchain.
- **Styling**: Tailwind CSS `3.4.19` with PostCSS and Autoprefixer.
- **Icons & Markdown**: Heroicons SVG library and custom React Markdown rendering with code blocks.

---

## Project Structure

```
CampusMind-AI/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes.py              # FastAPI endpoints (Auth, Docs, Chat, Metrics)
│   │   │   └── __init__.py
│   │   ├── core/
│   │   │   ├── auth.py                # JWT Bearer dependencies and RBAC policies
│   │   │   ├── database.py            # MySQL engine, connection pooling, and sessionmaker
│   │   │   └── security.py            # Bcrypt hashing, JWT generation, and token helpers
│   │   ├── models/
│   │   │   ├── db_models.py           # SQLAlchemy declarative ORM models
│   │   │   └── __init__.py
│   │   ├── repositories/
│   │   │   ├── database_repository.py # Database CRUD operations (Users, Docs, Sessions, Tokens)
│   │   │   └── __init__.py
│   │   ├── schemas/
│   │   │   ├── api_schemas.py         # Request and response Pydantic models
│   │   │   ├── chunk.py               # GroundedAnswer, ChunkMetadata, and SourceCitation schemas
│   │   │   └── __init__.py
│   │   ├── services/
│   │   │   ├── cache_service.py       # RedisCacheService, SHA-256 keys, direct key retrieval, LRU/LFU controls
│   │   │   ├── chat_service.py        # Conversation persistence and chat orchestration
│   │   │   ├── chunking_service.py    # Fixed, recursive, and semantic document splitters
│   │   │   ├── document_extractor.py  # Multi-format text extraction (PDF, DOCX, TXT)
│   │   │   ├── embedding_service.py   # BAAI/bge-small-en-v1.5 dense vector representations
│   │   │   ├── generation_service.py  # Grounded prompt construction and Groq LLM client
│   │   │   ├── hybrid_retrieval.py    # Reciprocal Rank Fusion of BM25 and Qdrant
│   │   │   ├── ingestion_service.py   # Multi-stage extraction, chunking, and indexing
│   │   │   ├── llm_service.py         # Base Groq client wrapper
│   │   │   ├── rag_service.py         # End-to-end RAG orchestrator with exact + semantic cache integration
│   │   │   ├── reranking_service.py   # BAAI/bge-reranker-base CrossEncoder reranker
│   │   │   ├── retrieval_bm25.py      # BM25Okapi lexical retrieval
│   │   │   ├── semantic_cache_service.py # Vector semantic caching (campusmind_semantic_cache in Qdrant)
│   │   │   ├── vector_store.py        # Qdrant client collection management and queries
│   │   │   └── __init__.py
│   │   ├── main.py                    # FastAPI application instance and middleware configuration
│   │   └── __init__.py
│   ├── evaluation/                    # Rigorous offline benchmark harness
│   │   ├── benchmark_questions.py     # 25-question golden benchmark set
│   │   ├── cache_comparison.py        # Cache hit vs miss latency evaluation
│   │   ├── chunking_comparison.py     # Fixed vs recursive vs semantic chunk evaluation
│   │   ├── corpus.py                  # Evaluation documents corpus
│   │   ├── metrics.py                 # Recall@K and MRR metric calculations
│   │   ├── real_redis_benchmark.py    # Live Redis Docker latency profiling
│   │   ├── report_generator.py        # Markdown benchmark report generation
│   │   ├── run_eval.py                # Command-line benchmark runner
│   │   └── results/                   # Verified evaluation reports and CSV logs
│   ├── tests/                         # Pytest test suite (122 unit & integration tests)
│   ├── storage/uploads/               # Uploaded document filesystem storage
│   ├── requirements.txt               # Backend Python dependencies
│   ├── .env.example                   # Environment configuration template
│   └── main.py                        # Uvicorn entry point
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── AdminDashboard.jsx     # System status, corpus metrics, service indicators
│   │   │   ├── AuthModal.jsx          # Login and student registration dialog
│   │   │   ├── CacheAnalytics.jsx     # Live hit rate, memory usage, and LRU/LFU toggle
│   │   │   ├── ChatPage.jsx           # Conversation interface with citations and cached badges
│   │   │   ├── DocumentManagement.jsx # Multi-format document upload and ingestion status
│   │   │   ├── HomePage.jsx           # Clean landing view with role guidance
│   │   │   ├── MarkdownRenderer.jsx   # Clean Markdown formatter for answers and citations
│   │   │   └── Navbar.jsx             # Navigation and user session status
│   │   ├── context/
│   │   │   └── AuthContext.jsx        # JWT storage, automatic token renewal, and authFetch
│   │   ├── App.jsx                    # Root application component and view routing
│   │   ├── main.jsx                   # React DOM application mount point
│   │   └── index.css                  # Tailwind styles and custom utilities
│   ├── index.html                     # Frontend single-page entry HTML
│   ├── package.json                   # NPM dependencies and build scripts
│   ├── tailwind.config.js             # Tailwind design configuration
│   └── vite.config.js                 # Vite development and proxy settings
├── docs/                              # Project specifications and architectural documents
├── .gitignore                         # Git-ignored directories and environment secrets
└── README.md                          # Project documentation
```

---

## Installation and Setup Instructions

### Prerequisites
- **Python**: Version `3.12` or higher.
- **Node.js**: Version `18.x` or higher with `npm`.
- **Docker Desktop** (or native services): For running Redis and Qdrant containers.
- **MySQL Server**: Version `8.0+` running locally on port `3306`.

### Step 1: Clone the Repository
```powershell
git clone https://github.com/your-username/CampusMind-AI.git
cd CampusMind-AI
```

### Step 2: Start Supporting Services (Redis, Qdrant, MySQL)

If using Docker Desktop, start Redis and Qdrant with:
```powershell
# Start Redis Container (port 6379)
docker run -d --name campusmind-redis -p 6379:6379 redis:7-alpine redis-server --maxmemory 100mb --maxmemory-policy allkeys-lru

# Start Qdrant Container (port 6333)
docker run -d --name campusmind-qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest
```

Ensure MySQL is running on port `3306` with a database named `campusmind`:
```sql
CREATE DATABASE IF NOT EXISTS campusmind CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Step 3: Backend Python Environment Setup
```powershell
cd CampusMind-AI\backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Frontend Node Environment Setup
```powershell
cd ..\frontend

# Install node dependencies
npm install
```

---

## Environment Configuration

Configure the backend environment file by creating `backend/.env` from the provided template:

```powershell
cd CampusMind-AI\backend
Copy-Item .env.example .env
```

Edit `backend/.env` with your local connection details:

```ini
APP_ENV=development

# Groq Cloud LLM
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b

# Redis Answer Cache Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=1800
REDIS_MAXMEMORY=100mb
REDIS_EVICTION_POLICY=allkeys-lru

# Semantic Cache Configuration (Qdrant)
SEMANTIC_CACHE_THRESHOLD=0.90
SEMANTIC_CACHE_COLLECTION=campusmind_semantic_cache

# MySQL Relational Database
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=campusmind
DATABASE_URL=mysql+pymysql://root:your_mysql_password@localhost:3306/campusmind

# Qdrant Vector Database
QDRANT_URL=http://localhost:6333

# JWT Authentication & Cryptography
JWT_SECRET=your_secure_random_jwt_secret_key_here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30
```

---

## Running the Application

### 1. Launch FastAPI Backend
From `CampusMind-AI/backend` with the virtual environment activated:
```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Base URL: `http://localhost:8000`
- Interactive Swagger Documentation: `http://localhost:8000/docs`
- Health Endpoint: `http://localhost:8000/health`

### 2. Launch React Frontend
From `CampusMind-AI/frontend` in a separate PowerShell terminal:
```powershell
npm run dev
```
- Application Web UI: `http://localhost:5173`

---

## API Endpoints

All protected endpoints require a Bearer token in the request header: `Authorization: Bearer <token>`.

### Authentication Routes
| Method | Endpoint | Access Role | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/register` | Public | Registers a new account (default: `student`; public admin self-assignment is rejected). |
| `POST` | `/auth/login` | Public | Authenticates credentials; issues short-lived access token and long-lived refresh token. |
| `POST` | `/auth/refresh` | Public | Renews expired access token using a valid, non-revoked refresh token. |
| `POST` | `/auth/logout` | Authenticated | Revokes the active refresh token session in MySQL. |
| `POST` | `/auth/me` | Authenticated | Returns profile information for the authenticated user. |

### Document Management Routes
| Method | Endpoint | Access Role | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/documents/upload` | Admin | Ingests `.pdf`, `.docx`, or `.txt` files; runs extraction, chunking, embedding, and indexing. |
| `GET` | `/documents` | Admin | Retrieves paginated records of uploaded documents and chunk counts. |

### Chat & Grounded RAG Routes
| Method | Endpoint | Access Role | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/chat/ask` | Student, Staff, Admin | Executes grounded RAG inquiry with Redis cache-aside lookup and inline citation generation. |
| `GET` | `/chat/sessions` | Authenticated | Lists conversation sessions owned by the authenticated user. |
| `GET` | `/chat/history/{id}` | Authenticated | Retrieves stored messages and citation metadata for a session. |

### System Health & Cache Telemetry
| Method | Endpoint | Access Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Public | Reports operational connectivity for MySQL, Redis, and Qdrant. |
| `GET` | `/metrics/cache` | Admin | Returns cache hit rate, avoided calls, used memory, limit, and active policy. |
| `POST` | `/metrics/cache/policy` | Admin | Dynamically switches Redis memory eviction policy between `allkeys-lru` and `allkeys-lfu`. |

---

## Testing and Evaluation

### Automated Backend Test Suite
CampusMind AI maintains an automated test suite verifying all critical components:

```powershell
# From CampusMind-AI/backend with venv activated
pytest tests/ -v
```

**Verified Test Coverage (122/122 Tests Passing)**:
- `test_api_endpoints.py`: Verifies authentication routes, document handling, and chat workflows.
- `test_auth_and_rbac.py`: Verifies password hashing, token signatures, role enforcement, and resource isolation.
- `test_token_renewal.py`: Verifies access-token expiration, seamless renewal, invalid token rejection, and logout revocation.
- `test_bm25.py`: Verifies lexical tokenization, frequency scoring, and ranking.
- `test_cache.py`: Verifies cache key normalization, serialization, TTL handling, and version scoping.
- `test_semantic_cache.py`: Verifies Qdrant semantic caching, cosine threshold filtering (>= 0.90), embedding reuse, scope/version isolation, and expired Redis entry fallbacks.
- `test_chunking.py`: Verifies character and boundary preservation for fixed, recursive, and semantic splitters.
- `test_database_persistence.py`: Verifies relational constraints and conversation persistence.
- `test_document_extractor.py`: Verifies extraction across `.pdf`, `.docx`, and `.txt` files.
- `test_embedding.py`: Verifies dense 384-dimensional vector calculations.
- `test_evaluation.py`: Verifies calculation of Recall@K and MRR metrics.
- `test_generation.py`: Verifies citation parsing, context injection, and grounding validation.
- `test_hybrid_retrieval.py`: Verifies reciprocal rank fusion scoring ($1/(60 + \text{rank})$).
- `test_reranking.py`: Verifies CrossEncoder model loading, pair scoring, metadata preservation, empty candidate handling, and Top-K filtering.
- `test_rag_service.py`: Verifies end-to-end RAG query flow, exact and semantic cache lookups, and cache population.
- `test_redis_integration.py`: Verifies live Redis operations, including real memory pressure eviction under LRU and LFU.
- `test_vector_store.py`: Verifies Qdrant collection creation, payload indexing, and search.

### Benchmark Evaluation Results
The system was evaluated against a standard 25-question golden benchmark set across an identical corpus of institutional policy documents:

#### 1. Chunking Method Performance Comparison
| Method | Chunks Created | Avg Tokens/Chunk | Recall@5 | MRR | Avg Retrieval Latency |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Fixed Size** | 8 | 58.0 | **1.0000** | **0.7685** | **1.13 ms** |
| **Recursive** | 8 | 58.0 | **1.0000** | **0.7685** | 2.55 ms |
| **Semantic** | 30 | 23.2 | 0.7222 | 0.6028 | 1.86 ms |

*Finding*: Fixed and Recursive chunking achieved 100% Recall@5 on the benchmark corpus. Fixed chunking achieved the fastest processing time (0.0004s) and lowest retrieval latency (1.13 ms).

#### 2. Redis Caching Performance (40-Request Replay Benchmark)
| Metric | Caching Disabled | Caching Enabled | Improvement / Delta |
| :--- | :---: | :---: | :--- |
| **Total Inquiries** | 40 | 40 | Identical 25 unique + 15 repeat queries |
| **Cache Hits / Misses** | 0 / 40 | 15 / 25 | **37.5% Hit Rate** |
| **Avg Cache Miss Latency** | 51.23 ms | 51.17 ms | Complete RAG generation |
| **Avg Cache Hit Latency** | N/A | **0.20 ms** | **99.61% Latency Reduction** |
| **Expensive LLM Inferences** | 40 | 25 | **15 LLM calls avoided (37.5% saved)** |

---

## Design Decisions and Trade-offs

1. **Reciprocal Rank Fusion (RRF) over Weighted Score Averaging**:
   - *Decision*: Combine Qdrant dense similarity scores and BM25 lexical scores using $1/(k + \text{rank})$ with $k=60$.
   - *Trade-off*: Discards raw score magnitudes in favor of relative rankings. This prevents cosine similarity and unbounded BM25 scores from skewing retrieval when score scales diverge.
2. **Cache-Aside over Read-Through**:
   - *Decision*: FastAPI coordinates cache reads, RAG fallback, and cache writes.
   - *Trade-off*: Requires cache lookup logic in the application code, but enables custom validation of grounding quality before caching and supports non-blocking fail-soft fallback.
3. **Knowledge-Base Version Namespacing over Mass Key Deletion**:
   - *Decision*: Invalidation uses a version identifier in the cache key (`v1`, `v2`).
   - *Trade-off*: Old entries remain in Redis until evicted by TTL or memory limits, but avoids expensive, blocking `KEYS *` sweeps or cluster flushes during document uploads.
4. **Approximate LRU/LFU over Strict Linked Lists**:
   - *Decision*: Relies on Redis sampling (`maxmemory-samples 10`).
   - *Trade-off*: Evictions are statistically approximate rather than strictly ordered, saving significant memory overhead while maintaining high hit rates.

---

## Limitations and Future Improvements

- **Multi-Candidate Semantic Cache Probing**: The current semantic cache retrieves the top nearest neighbor (`limit=1`). Extending this to probe multiple candidates (`limit=3` or `limit=5`) would allow checking secondary candidates if the top match's Redis key has expired or been evicted.
- **Asynchronous Document Processing**: Processing large multi-hundred-page documents currently occurs synchronously. Offloading ingestion to a Celery or ARQ background task queue would improve client responsiveness on heavy uploads.
- **Distributed Lock during Cache Population**: Under extreme concurrency, simultaneous misses for the same query could trigger duplicate LLM calls before the first response caches. Adding a Redis distributed lock (`redlock`) would prevent these redundant calls.
- **Multi-Modal Document Extraction**: Expanding ingestion to parse embedded tables, charts, and diagrams using vision models or specialized layout parsers would broaden knowledge coverage.

---

## Conclusion

CampusMind AI combines verified document grounding, hybrid search (Qdrant + BM25), and low-latency Redis answer caching into a cohesive academic knowledge assistant. By leveraging cache-aside architecture, role-based scope isolation, and configurable memory eviction, the platform delivers sub-millisecond responses on recurring inquiries while preserving verifiable attribution and authorization boundaries.
