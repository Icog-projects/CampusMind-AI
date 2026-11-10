"""CampusMind AI - Chunking Strategy Comparison Evaluator.

Compares fixed, recursive, and semantic chunking on indexing speed and retrieval accuracy.

Responsibilities:
Class ChunkingEvaluator:
1. ChunkingEvaluator.__init__(): Initializes chunk sizes, overlaps, and top-k evaluation parameters.
2. ChunkingEvaluator.evaluate_method(): Evaluates a specific chunking strategy across the corpus and benchmark questions.
3. ChunkingEvaluator.run_all(): Runs evaluation across all chunking methods and outputs structured comparison data.
"""

import time
import json
import csv
import os
import logging
from typing import Dict, Any, List, Optional

from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_bm25 import BM25RetrievalService
from app.services.vector_store import VectorStoreService
from app.services.hybrid_retrieval import HybridRetrievalService
from app.schemas.chunk import EmbeddedChunk

from evaluation.corpus import CORPUS_DOCUMENTS
from evaluation.benchmark_questions import BENCHMARK_QUESTIONS
from evaluation.metrics import calculate_recall_at_k, calculate_mrr

logger = logging.getLogger(__name__)


# Evaluates chunking methods on corpus indexing and hybrid retrieval metrics.
class ChunkingEvaluator:

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        chunk_size_tokens: int = 500,
        chunk_overlap_tokens: int = 75,
        top_k: int = 5,
    ):
        self.embedding_service = embedding_service
        self.chunk_size_tokens = chunk_size_tokens
        self.chunk_overlap_tokens = chunk_overlap_tokens
        self.top_k = top_k
        self.chunking_service = ChunkingService(
            embedding_service=self.embedding_service,
            default_chunk_size_tokens=chunk_size_tokens,
            default_chunk_overlap_tokens=chunk_overlap_tokens,
        )

    # Runs the full indexing and retrieval evaluation for a given chunking method.
    def evaluate_method(self, method: str) -> Dict[str, Any]:
        # Step 1: Chunk documents
        t0 = time.perf_counter()
        all_chunks = []
        for doc in CORPUS_DOCUMENTS:
            chunks = self.chunking_service.chunk_document(
                document=doc,
                method=method,
                chunk_size_tokens=self.chunk_size_tokens,
                chunk_overlap_tokens=self.chunk_overlap_tokens,
            )
            all_chunks.extend(chunks)
        chunking_time_s = time.perf_counter() - t0

        chunk_count = len(all_chunks)
        total_tokens = sum(c.metadata.token_count_approx or 0 for c in all_chunks)
        avg_tokens = round(total_tokens / chunk_count, 1) if chunk_count > 0 else 0
        total_chars = sum(c.metadata.character_count for c in all_chunks)
        avg_chars = round(total_chars / chunk_count, 1) if chunk_count > 0 else 0

        # Step 2: Build BM25 Index
        bm25_service = BM25RetrievalService()
        bm25_service.build_index(all_chunks)

        # Step 3: Build Vector Store (Qdrant in-memory)
        vector_store = VectorStoreService(collection_name=f"eval_{method}")
        embedded_chunks = []
        for c in all_chunks:
            # If embedding_service is available, compute vector, otherwise dummy orthogonal
            if self.embedding_service is not None:
                vec = self.embedding_service.embed_text(c.content)
            else:
                # Mock 384-d vector for fast testing
                vec = [0.01] * 384
            embedded_chunks.append(EmbeddedChunk(chunk=c, embedding=vec))

        vector_store.upsert_chunks(embedded_chunks)

        # Step 4: Hybrid Retrieval Service
        hybrid_service = HybridRetrievalService(
            bm25_service=bm25_service,
            vector_store=vector_store,
        )

        # Step 5: Execute benchmark queries
        recalls = []
        mrrs = []
        query_latencies = []

        for q in BENCHMARK_QUESTIONS:
            expected_docs = set(q["expected_doc_ids"])

            t_start = time.perf_counter()
            q_vec = None
            if self.embedding_service is not None:
                q_vec = self.embedding_service.embed_query(q["question"])
            else:
                q_vec = [0.01] * 384

            results = hybrid_service.search(
                query=q["question"],
                query_vector=q_vec,
                top_k=self.top_k,
            )
            lat = time.perf_counter() - t_start
            query_latencies.append(lat)

            # Only score answerable questions for retrieval quality
            if q["is_answerable"]:
                rec = calculate_recall_at_k(results, expected_docs, k=self.top_k)
                mrr = calculate_mrr(results, expected_docs, k=self.top_k)
                recalls.append(rec)
                mrrs.append(mrr)

        avg_recall = round(sum(recalls) / len(recalls), 4) if recalls else 0.0
        avg_mrr = round(sum(mrrs) / len(mrrs), 4) if mrrs else 0.0
        avg_latency_ms = round(sum(query_latencies) / len(query_latencies) * 1000.0, 2)

        return {
            "method": method,
            "chunk_count": chunk_count,
            "avg_chunk_tokens": avg_tokens,
            "avg_chunk_chars": avg_chars,
            "chunking_time_s": round(chunking_time_s, 4),
            "recall_at_5": avg_recall,
            "mrr": avg_mrr,
            "avg_retrieval_latency_ms": avg_latency_ms,
        }

    # Runs comparison across all three chunking methods.
    def run_all(self, output_dir: str = "evaluation") -> Dict[str, Any]:
        methods = ["fixed", "recursive", "semantic"]
        results = {}
        for m in methods:
            logger.info("Evaluating chunking method: %s...", m)
            results[m] = self.evaluate_method(m)

        os.makedirs(output_dir, exist_ok=True)
        json_path = os.path.join(output_dir, "chunking_comparison.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        csv_path = os.path.join(output_dir, "chunking_comparison.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "method", "chunk_count", "avg_chunk_tokens", "avg_chunk_chars",
                "chunking_time_s", "recall_at_5", "mrr", "avg_retrieval_latency_ms"
            ])
            writer.writeheader()
            for r in results.values():
                writer.writerow(r)

        return results

