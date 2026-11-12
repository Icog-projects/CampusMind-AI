# CampusMind AI - Technical Evaluation Report

**Scope:** Chunking method comparison (SRS Section 12.2) and Redis answer
caching (SRS Section 12.3), evaluated on the same document corpus and
benchmark queries.

## 1. Evaluation methodology

- **Chunking benchmark:** 25 fixed questions, with Redis disabled, comparing
  Fixed, Recursive, and Semantic chunking.
- **Caching benchmark:** 40 requests consisting of 25 unique benchmark queries
  and 15 repeats, comparing caching disabled and enabled.
- Metrics were calculated from execution logs. The harness uses real document
  extraction, chunking, embeddings, BM25, Qdrant search, RRF, reranking, and
  cache logic. Redis networking is mocked in memory for reproducibility, and
  `MockFastLLM` adds controlled 50 ms latency.

| Method | Chunks Created | Avg Tokens/Chunk | Avg Chars/Chunk | Chunking Time (s) | Recall@5 | MRR | Avg Retrieval Latency (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Fixed** | 8 | 58.0 | 296.5 | 0.0004s | 1.0 | 0.7685 | 1.13 ms |
| **Recursive** | 8 | 58.0 | 296.5 | 0.0007s | 1.0 | 0.7685 | 2.55 ms |
| **Semantic** | 30 | 23.2 | 121.7 | 13.9059s | 0.7222 | 0.6028 | 1.86 ms |

**Finding:** Fixed chunking provides the best measured balance of recall,
processing time, and retrieval latency. All three methods remain configurable.

## 2. Measured caching results

| Metric | Caching Disabled | Caching Enabled | Improvement / Delta |
| :--- | :--- | :--- | :--- |
| **Total Requests** | 40 | 40 | Exact same 40-request replay |
| **Cache Hits / Misses** | 0 / 40 | 15 / 25 | Hit Rate: **37.5%** |
| **Avg Latency (Miss)** | 51.23 ms | 51.17 ms | Consistent with full RAG pipeline |
| **Avg Latency (Hit)** | N/A (Always Miss) | **0.2 ms** | **99.61% latency reduction** |
| **LLM Calls Executed** | 40 | 25 | **15 expensive calls avoided** |

**Finding:** Repeated questions achieved a **37.5% hit rate**. Cache hits
returned in **0.2 ms**, a **99.61% latency reduction**, and avoided 15 LLM
calls. Cache misses remained consistent with the full RAG pipeline.

## 3. Implementation decisions

- **Fixed chunking is the default recommendation** because it achieved
  Recall@5 of 1.0, MRR of 0.7685, and the lowest measured retrieval latency.
- **Cache-aside** lets the application validate grounding before caching and
  fall back to the RAG pipeline if Redis is unavailable.
- **Exact caching uses deterministic keys.** Semantic caching uses a separate
  Qdrant collection with 384-dimensional cosine vectors, a default threshold
  of 0.90, and `scope` and `kb_version` filters.
- **Redis stores complete grounded answers and citations.** Qdrant stores
  semantic-cache metadata and document chunks, not answer payloads.
- **Ungrounded answers are not cached.** If a semantic match points to an
  expired or evicted Redis entry, the system falls through to RAG and
  repopulates both caches after producing a grounded answer.

## 4. Acceptance criteria

- [x] End-to-end document, chunk, and page traceability
- [x] BM25 and Qdrant retrieval combined with RRF
- [x] Inline citations in grounded answers
- [x] Evidence guard and no caching for insufficient context
- [x] Cache hits bypass embedding, retrieval, reranking, and generation
- [x] Metrics computed from execution logs rather than assumed gains

## 5. Environment classification

| Component | Implementation Type | Description & Role in Benchmark |
| :--- | :--- | :--- |
| **Document Extraction & Corpus** | **Real Production Code** | Native `ExtractedDocument` structures containing university handbooks, syllabi, and facility guides. |
| **Chunking Algorithms** | **Real Production Code** | Actual `Fixed`, `Recursive` (LangChain), and `Semantic` (Cosine similarity) algorithms executed independently. |
| **Embedding Service** | **Real Production Model** | Live `BAAI/bge-small-en-v1.5` sentence transformer computing real 384-dimensional vector embeddings on CPU. |
| **BM25 Retrieval** | **Real Production Code** | Real BM25Okapi inverted index scoring exact token matches and frequencies. |
| **Vector Store** | **Real Production Service** | Real `QdrantClient` in-memory collection executing cosine similarity vector search. |
| **Hybrid Fusion (RRF)** | **Real Production Code** | Real reciprocal rank fusion algorithm calculating $1/(k + \text{rank})$. |
| **Cache Service** | **Real Production Logic** | Real `RedisCacheService` hashing, namespace isolation, TTL handling, and JSON serialization. Redis network backend is mocked in-memory for reproducible, isolated benchmarking without external network variance. |
| **LLM Provider** | **Mocked Harness (`MockFastLLM`)** | Returns valid grounded response text and adds controlled 50 ms latency. Prevents quota depletion and non-deterministic remote network jitter during automated regression runs. |

## Conclusion

The measured results support Fixed chunking as the default configuration and
show that Redis answer caching substantially reduces latency and repeated LLM
work. The implementation preserves traceable evidence and avoids caching
unsupported answers, while the controlled harness makes the comparison
reproducible rather than a substitute for production monitoring.