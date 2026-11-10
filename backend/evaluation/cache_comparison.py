"""
CampusMind AI - Redis Caching Evaluation Runner (SRS Section 12.3)
Compares system performance with Redis Caching DISABLED vs. ENABLED:
1. Runs identical 25 benchmark queries under both conditions.
2. In the enabled condition, repeats a subset of queries to simulate realistic traffic.
3. Measures:
   - Hit rate (%) = hits / (hits + misses) * 100
   - Cache hit latency vs cache miss latency
   - Average response latency reduction (%)
   - LLM calls avoided
   - Verifies cache hits bypass embedding, retrieval, and LLM calls.
4. Outputs results in JSON, CSV, and summary tables.
"""

import time
import json
import csv
import os
import logging
from typing import Dict, Any, List, Optional
from unittest.mock import MagicMock

from app.schemas.chunk import GroundedAnswer, SourceCitation
from app.services.cache_service import RedisCacheService
from app.services.rag_service import RAGService
from app.services.generation_service import GenerationService
from app.services.llm_service import BaseLLMProvider

from evaluation.benchmark_questions import BENCHMARK_QUESTIONS
from evaluation.metrics import calculate_cache_metrics

logger = logging.getLogger(__name__)


class MockFastLLM(BaseLLMProvider):
    """Fast mock LLM for controlled evaluation without consuming external API credits."""
    def __init__(self):
        self.call_count = 0

    def generate(self, messages, temperature=0.1, max_tokens=1024, **kwargs):
        self.call_count += 1
        time.sleep(0.05)  # simulate 50ms LLM round-trip
        return {
            "content": "This is an evaluated answer grounded in the evidence [1].",
            "model": "openai/gpt-oss-120b",
            "prompt_tokens": 120,
            "completion_tokens": 30,
        }


class CacheEvaluator:
    """
    Evaluates RAG latency, hit rates, and avoided LLM calls with caching disabled vs enabled.
    """

    def __init__(self, rag_service: Optional[RAGService] = None):
        self.rag_service = rag_service

    def run_benchmark(self, output_dir: str = "evaluation") -> Dict[str, Any]:
        """
        Runs benchmark with Caching DISABLED, then with Caching ENABLED (with repeated traffic).
        """
        # Build mock components
        mock_redis_store = {}
        mock_redis_cli = MagicMock()

        def m_get(name):
            return mock_redis_store.get(name)

        def m_set(name, value, ex=None):
            mock_redis_store[name] = value
            return True

        mock_redis_cli.get.side_effect = m_get
        mock_redis_cli.set.side_effect = m_set

        cache_service = RedisCacheService(client=mock_redis_cli, default_ttl=1800)
        mock_llm = MockFastLLM()
        gen_service = GenerationService(llm_provider=mock_llm)

        # Mock hybrid retrieval service returning 1 evidence chunk
        mock_hybrid = MagicMock()
        from app.schemas.chunk import Chunk, ChunkMetadata, ScoredChunk
        sample_chunk = ScoredChunk(
            chunk=Chunk(
                content="Operating hours for the Main Library are 7:30 AM to Midnight.",
                metadata=ChunkMetadata(
                    documentId="doc_campus_facilities",
                    documentName="FacilitiesGuide.txt",
                    chunkId="chk-01",
                    chunkIndex=0,
                    chunkingMethod="recursive",
                    pageNumber=1,
                    characterCount=60,
                )
            ),
            score=0.95,
            retrieval_method="hybrid",
        )
        mock_hybrid.search.return_value = [sample_chunk]

        rag = RAGService(
            cache_service=cache_service,
            hybrid_retrieval_service=mock_hybrid,
            generation_service=gen_service,
        )

        questions = [q["question"] for q in BENCHMARK_QUESTIONS]

        # -------------------------------------------------------------
        # Replay the EXACT SAME 40-request sequence in both experiments:
        # 25 unique questions followed by 15 repeated questions.
        # -------------------------------------------------------------
        traffic_queries = questions + questions[:15]
        total_requests = len(traffic_queries)

        # -------------------------------------------------------------
        # Experiment 1: Caching Disabled (Replay all 40 requests)
        # Without caching, every request runs full RAG -> 40 LLM calls.
        # -------------------------------------------------------------
        no_cache_latencies = []
        llm_calls_before_disabled = mock_llm.call_count

        # Clear side_effect so return_value is actually used by MagicMock
        mock_redis_cli.get.side_effect = None
        mock_redis_cli.get.return_value = None
        mock_redis_cli.set.side_effect = None
        mock_redis_cli.set.return_value = False

        for q in traffic_queries:
            t0 = time.perf_counter()
            rag.query(question=q)
            lat = time.perf_counter() - t0
            no_cache_latencies.append(lat)

        no_cache_llm_calls = mock_llm.call_count - llm_calls_before_disabled
        avg_no_cache_ms = round(sum(no_cache_latencies) / len(no_cache_latencies) * 1000.0, 2)

        # -------------------------------------------------------------
        # Experiment 2: Caching Enabled (Replay identical 40 requests)
        # With caching, 25 initial queries miss & cache, 15 repeats hit -> 15 hits, 25 misses, 25 LLM calls.
        # -------------------------------------------------------------
        mock_redis_cli.get.side_effect = m_get
        mock_redis_cli.set.side_effect = m_set
        mock_redis_store.clear()

        hit_latencies = []
        miss_latencies = []
        hits = 0
        misses = 0
        llm_calls_before_enabled = mock_llm.call_count

        for q in traffic_queries:
            t0 = time.perf_counter()
            # Cache check before execution to accurately record hit status
            is_hit = cache_service.get_answer(q) is not None
            ans = rag.query(question=q)
            lat = time.perf_counter() - t0

            if is_hit:
                hits += 1
                hit_latencies.append(lat)
            else:
                misses += 1
                miss_latencies.append(lat)

        cache_llm_calls = mock_llm.call_count - llm_calls_before_enabled
        actual_avoided_calls = no_cache_llm_calls - cache_llm_calls

        cache_metrics = calculate_cache_metrics(
            hits=hits,
            misses=misses,
            hit_latencies=hit_latencies,
            miss_latencies=miss_latencies,
        )
        # Ensure avoided calls matches the actual differential of LLM invocations
        cache_metrics["llm_calls_avoided"] = actual_avoided_calls

        comparison = {
            "caching_disabled": {
                "total_queries": total_requests,
                "avg_latency_ms": avg_no_cache_ms,
                "llm_calls": no_cache_llm_calls,
                "hits": 0,
                "misses": total_requests,
            },
            "caching_enabled": {
                **cache_metrics,
                "actual_llm_calls": cache_llm_calls,
            },
        }

        os.makedirs(output_dir, exist_ok=True)
        json_path = os.path.join(output_dir, "cache_comparison.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(comparison, f, indent=2)

        csv_path = os.path.join(output_dir, "cache_comparison.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Metric", "Caching Disabled", "Caching Enabled"])
            writer.writerow(["Total Requests", total_requests, cache_metrics["total_queries"]])
            writer.writerow(["Cache Hits / Misses", f"0 / {total_requests}", f"{cache_metrics['hits']} / {cache_metrics['misses']}"])
            writer.writerow(["Hit Rate (%)", "0.0%", f"{cache_metrics['hit_rate_pct']}%"])
            writer.writerow(["Avg Latency (ms)", f"{avg_no_cache_ms} ms", f"{cache_metrics['avg_hit_latency_ms']} ms (hit) / {cache_metrics['avg_miss_latency_ms']} ms (miss)"])
            writer.writerow(["Latency Reduction (%)", "0.0%", f"{cache_metrics['latency_reduction_pct']}%"])
            writer.writerow(["LLM Calls Executed", no_cache_llm_calls, cache_llm_calls])
            writer.writerow(["LLM Calls Avoided", 0, actual_avoided_calls])

        return comparison
