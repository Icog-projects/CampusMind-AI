"""
CampusMind AI - Chat Service
Provides high-level business workflow for chat conversations:
- Coordinates session management and message logging
- Orchestrates with RAGService to produce grounded answers
- Persists both user and assistant interactions in MySQL (SRS Section 8.1, 9.1, FR-16)
  regardless of whether the answer is generated via LLM or served as a Redis cache hit.
"""

import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.schemas.chunk import GroundedAnswer
from app.services.rag_service import RAGService
from app.repositories.database_repository import ChatRepository

logger = logging.getLogger(__name__)


class ChatService:
    """
    Coordinates chat session lifecycle, interaction persistence, and RAG execution.
    """

    def __init__(self, db_session: Session, rag_service: Optional[RAGService] = None):
        self.db_session = db_session
        self.chat_repo = ChatRepository(db_session)
        self.rag_service = rag_service or RAGService()

    def ask(
        self,
        question: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        scope: str = "public",
        filter_document_id: Optional[str] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Processes a user question within a session:
        1. Ensures or creates the chat session.
        2. Persists the incoming user question in MySQL.
        3. Queries RAGService (which checks Redis cache before retrieval/generation).
        4. Detects whether the result was served from cache.
        5. Persists the assistant answer and source citations in MySQL with the is_cache_hit flag.
        6. Returns the answer, citations, session ID, and cache-hit status.
        """
        # Step 1: Ensure session exists or create one
        session_obj = None
        if session_id:
            session_obj = self.chat_repo.get_session(session_id)

        if not session_obj:
            session_title = question[:40] + "..." if len(question) > 40 else question
            session_obj = self.chat_repo.create_session(
                session_id=session_id,
                user_id=user_id,
                title=session_title,
            )

        active_session_id = session_obj.id

        # Step 2: Persist user question
        self.chat_repo.create_message(
            session_id=active_session_id,
            role="user",
            content=question,
            source_references=None,
            is_cache_hit=False,
        )

        # Step 3: Check cache status before RAG query to record accurate cache-hit flag
        is_hit = False
        try:
            is_hit = self.rag_service.cache_service.get_answer(question=question, scope=scope) is not None
        except Exception as e:
            logger.warning("Cache check error in ChatService: %s", e)

        # Step 4: Execute RAG query (or cache hit)
        grounded_answer: GroundedAnswer = self.rag_service.query(
            question=question,
            scope=scope,
            filter_document_id=filter_document_id,
            top_k=top_k,
        )

        # Step 5: Convert source citations to serializable dicts
        serializable_sources = [
            src.model_dump() for src in grounded_answer.sources
        ] if grounded_answer.sources else []

        # Step 6: Persist assistant response in MySQL with is_cache_hit indicator (SRS FR-16)
        assistant_msg = self.chat_repo.create_message(
            session_id=active_session_id,
            role="assistant",
            content=grounded_answer.answer,
            source_references=serializable_sources,
            is_cache_hit=is_hit,
        )

        return {
            "session_id": active_session_id,
            "message_id": assistant_msg.id,
            "answer": grounded_answer.answer,
            "sources": serializable_sources,
            "has_sufficient_context": grounded_answer.has_sufficient_context,
            "is_cache_hit": is_hit,
        }

