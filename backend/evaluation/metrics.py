"""CampusMind AI - Evaluation Metrics Utilities.

Calculates retrieval metrics (Recall@k, MRR) and cache performance metrics.

Responsibilities:
1. calculate_recall_at_k(): Computes fraction of expected document IDs present in top-k results.
2. calculate_mrr(): Computes Mean Reciprocal Rank based on the rank of the first relevant document.
3. calculate_cache_metrics(): Evaluates cache hit rate, avoided LLM invocations, and latency speedup.
"""

from typing import List, Sequence, Set, Dict, Any
from app.schemas.chunk import ScoredChunk


def calculate_recall_at_k(
    retrieved_chunks: Sequence[ScoredChunk],
    expected_doc_ids: Set[str],
    k: int = 5,
) -> float:
    """
    Computes Recall@k: Fraction of expected document IDs retrieved in top_k.
    If expected_doc_ids is empty (e.g. unanswerable query), returns 1.0 if no docs retrieved,
    or 1.0 (not applicable / vacuum truth).
    """
    if not expected_doc_ids:
        return 1.0  # vacuum truth for negative examples

    top_chunks = retrieved_chunks[:k]
    retrieved_docs = {chunk.chunk.metadata.document_id for chunk in top_chunks}
    hits = expected_doc_ids.intersection(retrieved_docs)
    return len(hits) / len(expected_doc_ids)


def calculate_mrr(
    retrieved_chunks: Sequence[ScoredChunk],
    expected_doc_ids: Set[str],
    k: int = 5,
) -> float:
    """
    Computes Mean Reciprocal Rank (MRR): 1 / rank of the first relevant document in top_k.
    Returns 0.0 if no relevant document is found within top_k.
    """
    if not expected_doc_ids:
        return 1.0

    for rank_idx, chunk in enumerate(retrieved_chunks[:k], start=1):
        if chunk.chunk.metadata.document_id in expected_doc_ids:
            return 1.0 / rank_idx
    return 0.0


def calculate_cache_metrics(
    hits: int,
    misses: int,
    hit_latencies: List[float],
    miss_latencies: List[float],
) -> Dict[str, Any]:
    """
    Computes cache performance metrics:
    - Hit rate (%) = hits / (hits + misses) * 100
    - Average hit latency (ms)
    - Average miss latency (ms)
    - Latency reduction (%)
    - LLM calls avoided (= hits)
    """
    total = hits + misses
    hit_rate = (hits / total * 100.0) if total > 0 else 0.0

    avg_hit_ms = (sum(hit_latencies) / len(hit_latencies) * 1000.0) if hit_latencies else 0.0
    avg_miss_ms = (sum(miss_latencies) / len(miss_latencies) * 1000.0) if miss_latencies else 0.0

    speedup = ((avg_miss_ms - avg_hit_ms) / avg_miss_ms * 100.0) if avg_miss_ms > 0.0 else 0.0

    return {
        "total_queries": total,
        "hits": hits,
        "misses": misses,
        "hit_rate_pct": round(hit_rate, 2),
        "avg_hit_latency_ms": round(avg_hit_ms, 2),
        "avg_miss_latency_ms": round(avg_miss_ms, 2),
        "latency_reduction_pct": round(speedup, 2),
        "llm_calls_avoided": hits,
    }

