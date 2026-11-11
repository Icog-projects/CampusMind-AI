"""CampusMind AI - Reranking Service.

Reranks candidate chunks retrieved from hybrid search using BAAI/bge-reranker-base.

Responsibilities:
Class RerankingService:
1. RerankingService.__init__(): Initializes the service and loads the CrossEncoder model singleton.
2. RerankingService._ensure_model_loaded(): Loads model into class-level singleton cache.
3. RerankingService.model(): Provides access to the underlying CrossEncoder instance.
4. RerankingService.rerank(): Scores (query, chunk) pairs and returns top K chunks sorted by descending relevance.
"""

import logging
from typing import List, Sequence, Optional
from sentence_transformers import CrossEncoder

from app.schemas.chunk import ScoredChunk

logger = logging.getLogger(__name__)

DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-base"
DEFAULT_RERANK_TOP_K = 5


# Scores and reranks hybrid retrieval candidate chunks using a cross-encoder model.
class RerankingService:
    _instance: Optional["RerankingService"] = None
    _model: Optional[CrossEncoder] = None

    # Initializes the RerankingService with model name and device.
    def __init__(
        self,
        model_name: str = DEFAULT_RERANKER_MODEL,
        device: str = "cpu",
        default_top_k: int = DEFAULT_RERANK_TOP_K,
    ):
        self.model_name = model_name
        self.device = device
        self.default_top_k = default_top_k
        self._ensure_model_loaded()

    # Loads model into class-level singleton cache to reuse across requests.
    def _ensure_model_loaded(self):
        if RerankingService._model is None:
            logger.info("Loading CrossEncoder model '%s' on %s...", self.model_name, self.device)
            RerankingService._model = CrossEncoder(self.model_name, device=self.device)
            logger.info("CrossEncoder model '%s' successfully loaded.", self.model_name)

    # Provides access to the underlying CrossEncoder instance.
    @property
    def model(self) -> CrossEncoder:
        if RerankingService._model is None:
            self._ensure_model_loaded()
        return RerankingService._model

    # Scores (query, chunk) pairs and returns top K chunks sorted by descending relevance.
    def rerank(
        self,
        query: str,
        candidates: Sequence[ScoredChunk],
        top_k: Optional[int] = None,
    ) -> List[ScoredChunk]:
        if not candidates:
            return []

        cleaned_query = (query or "").strip()
        if not cleaned_query:
            return list(candidates[: top_k or self.default_top_k])

        target_k = top_k if top_k is not None and top_k > 0 else self.default_top_k

        # Prepare (query, passage) text pairs for cross-encoder inference
        pairs = [(cleaned_query, candidate.chunk.content) for candidate in candidates]

        try:
            scores = self.model.predict(pairs)
        except Exception as e:
            logger.warning("Reranking prediction failed, falling back to original ordering: %s", e)
            return list(candidates[:target_k])

        # Pair candidates with their new reranking scores while preserving full metadata
        scored_pairs = []
        for candidate, score in zip(candidates, scores):
            reranked_chunk = ScoredChunk(
                chunk=candidate.chunk,
                score=float(score),
                retrieval_method="reranked",
            )
            scored_pairs.append(reranked_chunk)

        # Sort descending by relevance score
        scored_pairs.sort(key=lambda x: x.score, reverse=True)

        return scored_pairs[:target_k]

