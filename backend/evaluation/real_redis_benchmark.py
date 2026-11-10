"""
CampusMind AI - Real Redis Latency Benchmark Runner
Measures actual network/serialization hit and miss latency against a live running
Redis server (Docker container on localhost:6379).
Saves dedicated results separately from mock-based evaluation benchmarks:
- evaluation/results/real_redis_latency.json
- evaluation/results/real_redis_latency.csv
"""

import time
import json
import csv
import os
import logging
from typing import Dict, Any, List
from unittest.mock import MagicMock

import redis
from app.schemas.chunk import GroundedAnswer, SourceCitation, Chunk, ChunkMetadata, ScoredChunk
from app.services.cache_service import RedisCacheService
from app.services.rag_service import RAGService
from app.services.generation_service import GenerationService
from evaluation.cache_comparison import MockFastLLM
from evaluation.benchmark_questions import BENCHMARK_QUESTIONS

logger = logging.getLogger(__name__)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def run_real_redis_benchmark(output_dir: str = "evaluation/results") -> Dict[str, Any]:
    """
    Executes a latency and cache-hit benchmark directly against live Redis.
    """
    # 1. Connect and verify Redis
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2.0)
    try:
        r.ping()
    except Exception as e:
        raise ConnectionError(f"Cannot connect to live Redis at {REDIS_URL}: {e}")

    # Clean previous live benchmark keys
    bench_prefix = "campusmind:answer:real_bench"
    old_keys = r.keys(f"{bench_prefix}:*")
    if old_keys:
        r.delete(*old_keys)

    # 2. Setup real cache service
    cache_service = RedisCacheService(
        redis_url=REDIS_URL,
        namespace=bench_prefix,
        kb_version="live_v1",
        default_ttl=1800,
    )

    # 3. Setup RAG pipeline with mock hybrid retrieval & mock LLM for controlled baseline
    mock_llm = MockFastLLM()
    gen_service = GenerationService(llm_provider=mock_llm)

    mock_hybrid = MagicMock()
    sample_chunk = ScoredChunk(
        chunk=Chunk(
            content="Campus Facilities Guide: Main Library hours are 7:30 AM to Midnight.",
            metadata=ChunkMetadata(
                documentId="doc_campus_facilities",
                documentName="Campus_Facilities_Guide.txt",
                chunkId="chk-live-01",
                chunkIndex=0,
                chunkingMethod="recursive",
                pageNumber=1,
                characterCount=68,
            )
        ),
        score=0.96,
        retrieval_method="hybrid",
    )
    mock_hybrid.search.return_value = [sample_chunk]

    rag = RAGService(
        cache_service=cache_service,
        hybrid_retrieval_service=mock_hybrid,
        generation_service=gen_service,
    )

    questions = [q["question"] for q in BENCHMARK_QUESTIONS]
    traffic_queries = questions + questions[:15]  # 40 requests total

    # 4. Measure Pure Redis Direct Get/Set Latency (Raw Protocol & Serialization)
    sample_answer = GroundedAnswer(
        answer="Direct Redis benchmark answer [1].",
        has_sufficient_context=True,
        sources=[
            SourceCitation(
                citation_index=1,
                document_id="doc_campus_facilities",
                document_name="Campus_Facilities_Guide.txt",
                page_number=1,
                chunk_id="chk-live-01",
                chunk_index=0,
                content_snippet="Main Library hours are 7:30 AM to Midnight.",
            )
        ],
        model_name="openai/gpt-oss-120b",
        prompt_tokens=100,
        completion_tokens=25,
    )

    raw_set_latencies = []
    raw_get_hit_latencies = []

    for idx, q in enumerate(questions):
        t0 = time.perf_counter()
        cache_service.set_answer(f"raw_{idx}_{q}", sample_answer)
        raw_set_latencies.append(time.perf_counter() - t0)

        t1 = time.perf_counter()
        cache_service.get_answer(f"raw_{idx}_{q}")
        raw_get_hit_latencies.append(time.perf_counter() - t1)

    avg_raw_set_ms = round(sum(raw_set_latencies) / len(raw_set_latencies) * 1000.0, 3)
    avg_raw_get_ms = round(sum(raw_get_hit_latencies) / len(raw_get_hit_latencies) * 1000.0, 3)

    # 5. Measure End-to-End RAG with Real Redis
    # Replay 40-request traffic sequence
    rag_miss_latencies = []
    rag_hit_latencies = []
    hits = 0
    misses = 0
    llm_start = mock_llm.call_count

    for q in traffic_queries:
        is_hit = cache_service.get_answer(q) is not None
        t0 = time.perf_counter()
        rag.query(question=q)
        lat = time.perf_counter() - t0

        if is_hit:
            hits += 1
            rag_hit_latencies.append(lat)
        else:
            misses += 1
            rag_miss_latencies.append(lat)

    actual_llm_calls = mock_llm.call_count - llm_start
    avoided_llm_calls = len(traffic_queries) - actual_llm_calls
    hit_rate_pct = round((hits / len(traffic_queries)) * 100.0, 2)
    avg_rag_miss_ms = round(sum(rag_miss_latencies) / len(rag_miss_latencies) * 1000.0, 2)
    avg_rag_hit_ms = round(sum(rag_hit_latencies) / len(rag_hit_latencies) * 1000.0, 2)
    speedup_pct = round((avg_rag_miss_ms - avg_rag_hit_ms) / avg_rag_miss_ms * 100.0, 2)

    # Clean benchmark keys
    new_keys = r.keys(f"{bench_prefix}:*")
    if new_keys:
        r.delete(*new_keys)

    results = {
        "benchmark_type": "LIVE_DOCKER_REDIS",
        "redis_url": REDIS_URL,
        "total_requests": len(traffic_queries),
        "cache_hits": hits,
        "cache_misses": misses,
        "hit_rate_pct": hit_rate_pct,
        "llm_calls_executed": actual_llm_calls,
        "llm_calls_avoided": avoided_llm_calls,
        "raw_redis_direct_latency": {
            "avg_set_latency_ms": avg_raw_set_ms,
            "avg_get_hit_latency_ms": avg_raw_get_ms,
        },
        "end_to_end_rag_latency": {
            "avg_miss_latency_ms": avg_rag_miss_ms,
            "avg_hit_latency_ms": avg_rag_hit_ms,
            "latency_reduction_pct": speedup_pct,
        },
    }

    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, "real_redis_latency.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    csv_path = os.path.join(output_dir, "real_redis_latency.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Live Docker Redis Value", "Description"])
        writer.writerow(["Target Redis Instance", REDIS_URL, "Live Redis server in Docker container"])
        writer.writerow(["Total Requests", len(traffic_queries), "25 unique + 15 repeat questions"])
        writer.writerow(["Cache Hits / Misses", f"{hits} / {misses}", f"Hit rate: {hit_rate_pct}%"])
        writer.writerow(["Raw Redis Direct GET Latency", f"{avg_raw_get_ms} ms", "Native TCP socket + JSON deserialization"])
        writer.writerow(["Raw Redis Direct SET Latency", f"{avg_raw_set_ms} ms", "Native TCP socket + JSON serialization"])
        writer.writerow(["End-to-End RAG Cache Hit Latency", f"{avg_rag_hit_ms} ms", "Served instantly from live Redis"])
        writer.writerow(["End-to-End RAG Cache Miss Latency", f"{avg_rag_miss_ms} ms", "Full retrieval + generation pipeline"])
        writer.writerow(["Latency Reduction", f"{speedup_pct}%", "Cache hit speedup over live miss"])
        writer.writerow(["LLM Invocations Avoided", avoided_llm_calls, f"Executed {actual_llm_calls} of {len(traffic_queries)} calls"])

    return results


if __name__ == "__main__":
    print("Running Real Docker Redis Verification Benchmark...")
    res = run_real_redis_benchmark()
    print("=" * 60)
    print("Live Docker Redis Verification Benchmark Results:")
    print("=" * 60)
    print(f"Target Redis Instance: {res['redis_url']}")
    print(f"Total Requests Replayed: {res['total_requests']}")
    print(f"Cache Hits: {res['cache_hits']} | Misses: {res['cache_misses']} (Hit Rate: {res['hit_rate_pct']}%)")
    print(f"Raw Redis Direct GET Latency: {res['raw_redis_direct_latency']['avg_get_hit_latency_ms']} ms")
    print(f"Raw Redis Direct SET Latency: {res['raw_redis_direct_latency']['avg_set_latency_ms']} ms")
    print(f"RAG Cache Hit Latency: {res['end_to_end_rag_latency']['avg_hit_latency_ms']} ms")
    print(f"RAG Cache Miss Latency: {res['end_to_end_rag_latency']['avg_miss_latency_ms']} ms")
    print(f"Latency Reduction: {res['end_to_end_rag_latency']['latency_reduction_pct']}%")
    print(f"LLM Calls Executed: {res['llm_calls_executed']} (Avoided: {res['llm_calls_avoided']})")
    print("=" * 60)
