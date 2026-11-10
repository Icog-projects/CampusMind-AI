"""
Tests for CampusMind AI Evaluation Framework.
Verifies:
1. Metric calculations: Recall@k and MRR.
2. Cache metrics calculations (hit rate, latency reduction, avoided LLM calls).
3. Chunking evaluation runner generates valid comparison results without error.
4. Cache evaluation runner simulates traffic and records accurate metrics.
5. Evaluation markdown report generation formats comparison tables accurately.
"""

import pytest
from evaluation.metrics import calculate_recall_at_k, calculate_mrr, calculate_cache_metrics
from evaluation.report_generator import generate_evaluation_markdown
from evaluation.chunking_comparison import ChunkingEvaluator
from evaluation.cache_comparison import CacheEvaluator
from app.schemas.chunk import Chunk, ChunkMetadata, ScoredChunk


def make_scored(doc_id: str, chunk_id: str, rank_score: float) -> ScoredChunk:
    return ScoredChunk(
        chunk=Chunk(
            content="Sample evaluation text content",
            metadata=ChunkMetadata(
                documentId=doc_id,
                documentName=f"{doc_id}.pdf",
                chunkId=chunk_id,
                chunkIndex=0,
                chunkingMethod="recursive",
                characterCount=30,
            ),
        ),
        score=rank_score,
        retrieval_method="hybrid",
    )


def test_recall_at_k_calculation():
    """Verify Recall@k correctly measures retrieved fraction."""
    # Expected docs: doc_A, doc_B
    expected = {"doc_A", "doc_B"}

    # Result contains only doc_A in top 2 -> Recall@2 is 0.5
    chunks = [
        make_scored("doc_A", "c1", 1.0),
        make_scored("doc_C", "c2", 0.8),
        make_scored("doc_B", "c3", 0.6),
    ]

    recall_at_2 = calculate_recall_at_k(chunks, expected, k=2)
    assert recall_at_2 == 0.5

    # With k=3, both doc_A and doc_B are present -> Recall@3 is 1.0
    recall_at_3 = calculate_recall_at_k(chunks, expected, k=3)
    assert recall_at_3 == 1.0

    # Negative unanswerable queries return 1.0
    assert calculate_recall_at_k(chunks, set(), k=3) == 1.0


def test_mrr_calculation():
    """Verify Mean Reciprocal Rank (MRR) reflects rank of first relevant doc."""
    expected = {"doc_target"}

    # First result is target -> rank 1 -> MRR = 1/1 = 1.0
    chunks_rank1 = [make_scored("doc_target", "c1", 1.0)]
    assert calculate_mrr(chunks_rank1, expected, k=5) == 1.0

    # Target is second -> rank 2 -> MRR = 1/2 = 0.5
    chunks_rank2 = [make_scored("doc_other", "c0", 1.0), make_scored("doc_target", "c1", 0.9)]
    assert calculate_mrr(chunks_rank2, expected, k=5) == 0.5

    # Target not in top 2 -> MRR = 0.0
    assert calculate_mrr(chunks_rank2, expected, k=1) == 0.0


def test_cache_metrics_calculation():
    """Verify hit rate and latency reduction calculations."""
    metrics = calculate_cache_metrics(
        hits=15,
        misses=25,
        hit_latencies=[0.005] * 15,   # 5ms
        miss_latencies=[0.100] * 25,  # 100ms
    )

    # 15 / (15 + 25) = 15/40 = 37.5%
    assert metrics["hit_rate_pct"] == 37.5
    assert metrics["hits"] == 15
    assert metrics["misses"] == 25
    assert metrics["llm_calls_avoided"] == 15
    assert metrics["avg_hit_latency_ms"] == 5.0
    assert metrics["avg_miss_latency_ms"] == 100.0
    # (100 - 5) / 100 = 95.0% latency reduction
    assert metrics["latency_reduction_pct"] == 95.0


def test_chunking_evaluator_execution(tmp_path):
    """Verify chunking evaluator runs all methods and generates valid metrics."""
    evaluator = ChunkingEvaluator()
    results = evaluator.run_all(output_dir=str(tmp_path))

    assert "fixed" in results
    assert "recursive" in results
    assert "semantic" in results

    for method, data in results.items():
        assert data["chunk_count"] > 0
        assert data["recall_at_5"] >= 0.0
        assert data["mrr"] >= 0.0
        assert data["avg_retrieval_latency_ms"] >= 0.0


def test_cache_evaluator_execution(tmp_path):
    """Verify cache evaluator executes traffic benchmark and captures bypass."""
    evaluator = CacheEvaluator()
    res = evaluator.run_benchmark(output_dir=str(tmp_path))

    assert "caching_disabled" in res
    assert "caching_enabled" in res
    assert res["caching_enabled"]["hits"] == 15
    assert res["caching_enabled"]["llm_calls_avoided"] == 15
    assert res["caching_enabled"]["avg_hit_latency_ms"] < res["caching_enabled"]["avg_miss_latency_ms"]


def test_markdown_report_formatting():
    """Verify generated markdown contains proper tables and acceptance criteria."""
    chunk_res = {
        "recursive": {
            "chunk_count": 8,
            "avg_chunk_tokens": 120.5,
            "avg_chunk_chars": 510.0,
            "chunking_time_s": 0.015,
            "recall_at_5": 0.94,
            "mrr": 0.88,
            "avg_retrieval_latency_ms": 3.45,
        }
    }
    cache_res = {
        "caching_disabled": {"total_queries": 25, "avg_latency_ms": 125.0, "llm_calls": 25},
        "caching_enabled": {
            "total_queries": 40,
            "hits": 15,
            "misses": 25,
            "hit_rate_pct": 37.5,
            "avg_hit_latency_ms": 2.5,
            "avg_miss_latency_ms": 120.0,
            "latency_reduction_pct": 97.9,
            "llm_calls_avoided": 15,
            "actual_llm_calls": 25,
        },
    }

    report = generate_evaluation_markdown(chunk_res, cache_res)
    assert "# CampusMind AI - Technical Evaluation Report" in report
    assert "| **Recursive** |" in report
    assert "37.5%" in report
    assert "15 expensive calls avoided" in report

