# Caching Reading Assignment: Summary & Architectural Justification

This document provides a concise theoretical review of caching patterns, lifecycle management, and eviction algorithms, followed by an architectural justification of the caching choices implemented in **CampusMind AI**.

---

## 1. Caching Strategies

### Read Strategies: Cache-Aside vs. Read-Through

| Strategy | How It Works | Key Advantages | Trade-offs & Disadvantages |
| :--- | :--- | :--- | :--- |
| **Cache-Aside** *(Lazy Loading)* | The application orchestrates reads. It checks the cache first; on a miss, it queries the backend store, populates the cache, and returns data. | Resilient to cache failure (fails soft to database); supports heterogeneous data shaping (e.g. pre-serialized JSON). | Cache miss penalty (two network hops); application logic must manage cache reads and writes. |
| **Read-Through** | The application queries the cache layer as its primary store. The cache itself intercepts misses and loads data from the database. | Simplifies application code; standardizes data access across services. | Tight coupling to cache proxy/plugin; cached schema is strictly bound to database record schema. |

### Write Strategies: Write-Through vs. Write-Behind vs. Write-Around

| Strategy | Write Target & Order | Key Advantages | Trade-offs & Disadvantages |
| :--- | :--- | :--- | :--- |
| **Write-Through** | Synchronously writes to Cache **and** Database within a single operation. | High consistency; no data divergence between cache and database. | Higher write latency (sum of cache and database write times). |
| **Write-Behind** *(Write-Back)* | Writes to Cache immediately; writes to Database are queued and batched asynchronously. | Lowest write latency; absorbs heavy write bursts. | Risk of data loss if cache fails before dirty entries are committed. |
| **Write-Around** | Writes directly to Database, bypassing Cache completely. | Prevents cache pollution from write-heavy data that is rarely read. | Initial reads on new data encounter cache misses. |

---

## 2. Cache Management: TTL, Invalidation, and Eviction

- **TTL (Time-To-Live)**: A fixed time duration set on a key. Redis automatically purges expired keys via passive access checks and active periodic sampling. Establishes an upper bound on stale data life.
- **Cache Invalidation**: Explicit revocation or deletion of cached data triggered by an event (e.g. data update or document re-indexing) to guarantee semantic freshness.
- **Eviction**: Resource-driven reclamation of active keys triggered when cache memory hits a configured limit (`maxmemory`).

### Critical Distinction: Invalidation vs. Eviction
- **Invalidation is data-driven**: It occurs because source data has changed or become outdated. It happens regardless of memory consumption.
- **Eviction is resource-driven**: It occurs purely because storage space is exhausted. Valid, fresh keys are removed to keep the server operational.

---

## 3. Eviction Policies: LRU, LFU, FIFO, and Random

| Policy | Eviction Basis | Ideal Workload | Primary Disadvantage |
| :--- | :--- | :--- | :--- |
| **LRU** *(Least Recently Used)* | Evicts keys whose last access timestamp (`idletime`) is oldest. | Conversational queries, trending announcements, temporal access patterns. | Susceptible to cache pollution during one-off full-table sweeps. |
| **LFU** *(Least Frequently Used)* | Evicts keys with the lowest logarithmic access frequency counter. | Core degree criteria, recurring institutional policies, stable hot keys. | Slow to decay historically popular keys that fall out of favor. |
| **FIFO** *(First In, First Out)* | Evicts keys strictly based on insertion order, ignoring access frequency/recency. | Ephemeral ingestion streams, time-series logging buffers. | Inefficient hit rates; frequently requested hot keys are evicted simply because they are old. |
| **Random** | Randomly selects candidate keys to evict. | Uniform, unpredictable access patterns with minimal CPU budget. | Poor hit rates; high probability of evicting active hot keys. |

---

## 4. Redis Eviction Policies & Standard Support

Redis enforces memory thresholds through the `maxmemory` configuration directive. When memory usage reaches `maxmemory`, Redis executes one active eviction policy from its **eight standard options**:

| Redis Eviction Policy | Key Candidate Pool | Eviction Behavior |
| :--- | :--- | :--- |
| `noeviction` | All keys | Returns OOM errors for writes that allocate memory; read/del commands still work. |
| `allkeys-lru` | All keys | Evicts least recently used keys across the entire keyspace (approximate sampling). |
| `allkeys-lfu` | All keys | Evicts least frequently used keys across the entire keyspace (approximate Morris counter). |
| `allkeys-random` | All keys | Randomly evicts keys across the entire keyspace. |
| `volatile-lru` | Keys with an explicit TTL (`expire`) | Evicts least recently used keys among expiring keys. |
| `volatile-lfu` | Keys with an explicit TTL (`expire`) | Evicts least frequently used keys among expiring keys. |
| `volatile-random` | Keys with an explicit TTL (`expire`) | Randomly evicts keys among expiring keys. |
| `volatile-ttl` | Keys with an explicit TTL (`expire`) | Evicts keys with the shortest remaining TTL (closest to expiry). |

> **Redis FIFO Clarification**: Redis **does not** provide a native `allkeys-fifo` or `volatile-fifo` eviction policy. FIFO semantics must be implemented at the application layer using Redis `LIST` (`LPUSH`/`RPOP`) or sorted sets (`ZSET`) with insertion timestamps.

---

## 5. CampusMind AI Implementation Choices & Justification

Inspection of `backend/app/services/cache_service.py`, `backend/app/services/rag_service.py`, and `backend/.env.example` confirms the following architecture:

1. **Caching Strategy: Cache-Aside with Write-Around**:
   - *Read Path*: `RAGService.query()` first checks Redis via `cache_service.get_answer()`. On a hit, it returns the serialized `GroundedAnswer` in ~0.5 ms. On a miss, it executes hybrid retrieval, reranking, and Groq LLM generation.
   - *Write Path*: Administrative document uploads write directly to MySQL and Qdrant (Write-Around), avoiding cache pollution with unqueried documents.
   - *Grounding Guard*: Answers are only committed to Redis (`cache_service.set_answer()`) if `has_sufficient_context` is true and source citations exist. Low-confidence negatives are never cached.

2. **Eviction Policy: Configurable `allkeys-lru` & `allkeys-lfu` (`REDIS_MAXMEMORY=100mb`)**:
   - Configured with `DEFAULT_MAXMEMORY = "100mb"` and `DEFAULT_EVICTION_POLICY = "allkeys-lru"`.
   - Administrators can dynamically switch policies at runtime (`allkeys-lru` vs `allkeys-lfu`) via `POST /metrics/cache/policy`, allowing empirical comparison between recency and frequency eviction under high load.

3. **Deterministic Cache Key Specification**:
   - `Key = namespace:kb_version:scope:SHA256(normalized_question)`
   - *Scope Isolation*: Distinguishes `public` (students) from `all` (staff/admin), preventing privilege leakage.
   - *Knowledge-Base Versioning*: Uses `DEFAULT_KB_VERSION="v1"`. Updating the version string atomically shifts the cache namespace, achieving instant invalidation without issuing blocking `KEYS *` or `FLUSHDB` commands.

4. **Temporal Expiration (TTL)**:
   - Configured via `REDIS_CACHE_TTL = 1800` (30 minutes default) to ensure periodic freshness without manual admin intervention.

---

## 6. Trade-offs and Conclusion

### Architectural Fit
- **Low Latency & Cost Elimination**: Cache-aside avoids repeated BGE-small embeddings, BM25 searches, Qdrant vector scans, Cross-Encoder reranking, and Groq LLM calls, reducing inquiry latency from ~50 ms down to sub-millisecond speeds.
- **Fail-Soft Reliability**: If Redis becomes unreachable, `RAGService` catches the exception and falls back to live retrieval without disrupting user sessions.
- **Memory Safety**: Configuring `maxmemory 100mb` alongside `allkeys-lru`/`allkeys-lfu` ensures the instance never crashes from OOM errors during traffic surges.

### Limitations & Trade-offs
- **Exact vs. Paraphrased Matching**: SHA-256 keys only match exact normalized strings (handled separately by our Qdrant semantic cache layer for paraphrased queries).
- **Sampling Approximations**: Redis uses sample-based eviction (`maxmemory-samples 5–10`) rather than a strict global linked list, trading absolute eviction precision for minimal memory overhead.
- **Cold Cache Penalty**: Initial inquiries or post-invalidation queries invariably incur full RAG pipeline latency.

