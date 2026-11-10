"""
CampusMind AI - MySQL Database Integration Tests
Tests actual MySQL database operations on localhost:3306/campusmind:
- Table schema creation and verification
- DocumentRepository CRUD operations (create, read, filter, update status/version, delete)
- ChatRepository CRUD operations (sessions, messages, foreign-key relationships, cascade deletes)
- Verified chat interaction persistence for both cache misses and cache hits (SRS Section 8.1, 9.1, FR-16)
- Foreign key constraints enforcement
- Index verification
"""

import os
import uuid
import pytest
from sqlalchemy import inspect, text

from app.core.database import get_engine, get_session_factory, init_db
from app.models.db_models import DocumentModel, ChatSessionModel, MessageModel
from app.repositories.database_repository import DocumentRepository, ChatRepository
from app.services.chat_service import ChatService
from app.services.rag_service import RAGService
from app.services.cache_service import RedisCacheService
from app.schemas.chunk import GroundedAnswer, SourceCitation


def is_mysql_available() -> bool:
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not is_mysql_available(),
    reason="MySQL server not available on localhost:3306/campusmind"
)


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Ensures tables exist before running database tests."""
    engine = get_engine()
    init_db(engine)
    yield


@pytest.fixture
def db_session():
    """Provides a fresh database session for each test and rolls back/cleans up test data."""
    factory = get_session_factory()
    session = factory()
    yield session
    session.close()


def test_mysql_table_creation_and_indexes():
    """Verifies all required tables and indexes exist in the real MySQL database."""
    engine = get_engine()
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    assert "documents" in tables
    assert "chat_sessions" in tables
    assert "messages" in tables

    # Check indexes on documents
    doc_indexes = {idx["name"]: idx["column_names"] for idx in inspector.get_indexes("documents")}
    assert "ix_documents_status" in doc_indexes
    assert "ix_documents_version" in doc_indexes

    # Check indexes on chat_sessions
    session_indexes = {idx["name"]: idx["column_names"] for idx in inspector.get_indexes("chat_sessions")}
    assert "ix_chat_sessions_user_id" in session_indexes
    assert "ix_chat_sessions_created_at" in session_indexes

    # Check indexes on messages
    msg_indexes = {idx["name"]: idx["column_names"] for idx in inspector.get_indexes("messages")}
    assert "ix_messages_session_id_created_at" in msg_indexes
    assert "ix_messages_is_cache_hit" in msg_indexes


def test_document_repository_crud(db_session):
    """Verifies CRUD operations for DocumentRepository against live MySQL."""
    repo = DocumentRepository(db_session)
    doc_id = f"test_doc_{uuid.uuid4().hex[:8]}"

    # Create
    doc = repo.create_document(
        document_id=doc_id,
        filename="CS_Handbook_2026.pdf",
        file_path="/storage/uploads/CS_Handbook_2026.pdf",
        uploader_id="user_admin",
        status="uploaded",
        chunk_count=8,
        version="v1",
    )
    assert doc.id == doc_id
    assert doc.status == "uploaded"

    # Read
    fetched = repo.get_by_id(doc_id)
    assert fetched is not None
    assert fetched.filename == "CS_Handbook_2026.pdf"

    # Update
    updated = repo.update_status(document_id=doc_id, status="processed", chunk_count=10, version="v2")
    assert updated.status == "processed"
    assert updated.chunk_count == 10
    assert updated.version == "v2"

    # Filtered list
    docs_v2 = repo.list_documents(version="v2")
    assert any(d.id == doc_id for d in docs_v2)

    # Delete
    deleted = repo.delete_document(doc_id)
    assert deleted is True
    assert repo.get_by_id(doc_id) is None


def test_chat_repository_and_cascade_delete(db_session):
    """Verifies session and message creation, relationships, and cascade deletion."""
    repo = ChatRepository(db_session)
    session_id = f"sess_{uuid.uuid4().hex[:8]}"

    # Create session
    chat_sess = repo.create_session(
        session_id=session_id,
        user_id="student_123",
        title="Graduation Policy Question",
    )
    assert chat_sess.id == session_id

    # Create user message
    user_msg = repo.create_message(
        session_id=session_id,
        role="user",
        content="What is the minimum CGPA required?",
        is_cache_hit=False,
    )

    # Create assistant message with structured sources and cache-hit flag
    sources = [
        {
            "citation_index": 1,
            "document_id": "doc_handbook_cs",
            "document_name": "CS_Handbook.pdf",
            "page_number": 2,
            "chunk_id": "chk-02",
            "content_snippet": "CGPA of 2.0 required for good standing.",
        }
    ]
    asst_msg = repo.create_message(
        session_id=session_id,
        role="assistant",
        content="A minimum CGPA of 2.0 is required [1].",
        source_references=sources,
        is_cache_hit=True,
    )

    # Fetch messages in order
    history = repo.get_session_messages(session_id)
    assert len(history) == 2
    assert history[0].role == "user"
    assert history[1].role == "assistant"
    assert history[1].is_cache_hit is True
    assert history[1].source_references[0]["document_id"] == "doc_handbook_cs"

    # Cascade delete session
    deleted = repo.delete_session(session_id)
    assert deleted is True

    # Confirm session and messages are deleted from MySQL
    assert repo.get_session(session_id) is None
    assert len(repo.get_session_messages(session_id)) == 0


def test_chat_interaction_persistence_on_cache_hit_and_miss(db_session):
    """
    Verifies SRS Section 8.1 / FR-16 requirement:
    Save the current user's chat interaction in MySQL on BOTH cache hits and misses.
    """
    from unittest.mock import MagicMock

    # Setup mock RAG pipeline where query 1 is a miss, and query 2 is a hit
    mock_cache = MagicMock()
    # First call: cache miss (None), second call: cache hit
    cached_grounded_answer = GroundedAnswer(
        answer="A minimum CGPA of 2.0 is required [1].",
        has_sufficient_context=True,
        sources=[
            SourceCitation(
                citation_index=1,
                document_id="doc_handbook_cs",
                document_name="CS_Handbook_2026.pdf",
                page_number=2,
                chunk_id="chk-cgpa",
                chunk_index=0,
                content_snippet="CGPA of 2.0 is required.",
            )
        ],
    )

    mock_cache.get_answer.side_effect = [None, cached_grounded_answer, cached_grounded_answer]

    mock_rag = MagicMock()
    mock_rag.cache_service = mock_cache
    mock_rag.query.return_value = cached_grounded_answer

    chat_service = ChatService(db_session=db_session, rag_service=mock_rag)
    session_id = f"test_flow_{uuid.uuid4().hex[:8]}"

    # Interaction 1: Cache Miss
    res1 = chat_service.ask(
        question="What is the CGPA requirement?",
        session_id=session_id,
        user_id="user_test",
    )
    assert res1["is_cache_hit"] is False

    # Interaction 2: Cache Hit
    res2 = chat_service.ask(
        question="What is the CGPA requirement?",
        session_id=session_id,
        user_id="user_test",
    )
    assert res2["is_cache_hit"] is True

    # Verify both interactions are saved in MySQL
    chat_repo = ChatRepository(db_session)
    messages = chat_repo.get_session_messages(session_id)
    assert len(messages) == 4  # 2 user queries + 2 assistant responses

    # Check assistant message flags
    assistant_msgs = [m for m in messages if m.role == "assistant"]
    assert len(assistant_msgs) == 2
    assert assistant_msgs[0].is_cache_hit is False
    assert assistant_msgs[1].is_cache_hit is True

    # Cleanup test session
    chat_repo.delete_session(session_id)

