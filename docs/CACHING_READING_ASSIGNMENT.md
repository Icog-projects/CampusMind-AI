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

