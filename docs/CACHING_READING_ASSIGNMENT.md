# Caching Reading Assignment

## 1. Read strategies: cache-aside vs. read-through

| Strategy | Operation | Strengths | Trade-offs |
| :--- | :--- | :--- | :--- |
| **Cache-aside** (lazy loading) | The application checks the cache. On a miss, it reads the backend, returns the result, and populates the cache. | Flexible cached formats; cache failure can fall back to the backend. | The application manages cache reads and writes; misses add a backend round trip. |
| **Read-through** | The application reads only through the cache; the cache loads the backend automatically on a miss. | Simpler application code and centralized loading. | More dependent on cache infrastructure; cached data usually follows the backend schema. |

**CampusMind AI uses cache-aside.** FastAPI checks Redis with a deterministic
question key. On a miss it runs embedding, BM25, Qdrant, RRF, reranking, and
Groq generation. Only a sufficiently grounded answer with sources is cached.
If Redis is unavailable, the service fails soft and continues with live RAG.

## 2. Write strategies

| Strategy | Write path | Main benefit | Main risk or cost |
| :--- | :--- | :--- | :--- |
| **Write-through** | Write to cache and database synchronously. | Strong consistency and warm subsequent reads. | Higher write latency. |
| **Write-behind / write-back** | Write to cache first; persist to the database asynchronously. | Very low write latency and good burst absorption. | Eventual consistency and possible data loss before a flush. |
| **Write-around** | Write directly to the database; populate cache only after a later read. | Avoids polluting the cache with rarely read writes. | The first read after a write is a miss. |

CampusMind AI uses **write-around** for administrative document ingestion:
documents and vectors are written to MySQL and Qdrant, while synthesized
answers are created and cached only when users ask questions.

## 3. TTL, invalidation, and eviction

- **TTL (time-to-live)** expires a key after a fixed duration. It limits how
  long an answer can remain stale, but does not immediately react to source
  changes.
- **Invalidation** deliberately makes cached data unusable when its source
  changes. CampusMind AI uses the knowledge-base version in its cache namespace
  (`v1`); changing the version invalidates old answers without a blocking
  `KEYS *` or `FLUSHDB`.
- **Eviction** removes otherwise valid keys when Redis reaches its memory limit.
  CampusMind AI configures `maxmemory 100mb` and uses configurable LRU/LFU
  policies to prevent out-of-memory failures.

## 4. Eviction algorithms

| Algorithm | Selection rule | Advantage | Limitation |
| :--- | :--- | :--- | :--- |
| **LRU** | Removes the least recently accessed key. | Adapts quickly to changing or trending queries. | One-time scans can displace useful entries. |
| **LFU** | Removes the least frequently accessed key. | Preserves consistently popular queries. | Old popularity can remain influential after demand changes. |
| **FIFO** | Removes the oldest inserted key. | Simple and inexpensive. | Can remove frequently used hot keys. |
| **Random** | Removes an arbitrary key. | Minimal tracking and CPU overhead. | Usually produces a lower hit rate. |

LRU is suitable for changing conversational workloads; LFU is better for
stable, repeatedly requested policies. FIFO and random are simpler but are
less appropriate for CampusMind AI's mixed and uneven question traffic.

## 5. Redis support and application trade-offs

Redis supports these policies:

`noeviction`, `allkeys-lru`, `allkeys-lfu`, `allkeys-random`,
`volatile-lru`, `volatile-lfu`, `volatile-random`, and `volatile-ttl`.

`allkeys-*` policies consider all keys; `volatile-*` policies consider only
keys with a TTL. Redis runs one policy at a time and uses approximate sampling,
not an exact global ordering. Redis has no native FIFO eviction policy; FIFO
requires an application-level `LIST` or `ZSET`.

| CampusMind AI choice | Justification |
| :--- | :--- |
| Redis cache-aside | Allows grounding checks before caching and fail-soft recovery. |
| SHA-256 normalized query keys | Prevents key collisions and separates `public` and `all` access scopes. |
| Knowledge-base versioning | Invalidates old answers without expensive mass deletion. |
| 30-minute TTL (`1800s`) | Balances freshness, hit rate, and memory use. |
| `allkeys-lru` / `allkeys-lfu` | Protects Redis under memory pressure while allowing recency/frequency comparison. |
| Grounding guard | Prevents unsupported or low-confidence answers from being cached. |

Overall, these choices favor low latency and resilience while preserving
authorization boundaries and answer freshness.
