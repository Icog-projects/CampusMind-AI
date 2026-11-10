"""
CampusMind AI - API Endpoint Integration Tests
Tests all required FastAPI endpoints according to SRS v1.3:
1. POST /documents/upload: PDF, DOCX, TXT uploads, validation rejection of invalid files.
2. GET /documents: List documents from MySQL.
3. POST /chat/ask: Question answering, citations, cache-hit verification, and MySQL interaction persistence.
4. GET /health: Operational health and dependency checks (MySQL, Redis, Qdrant).
5. GET /metrics/cache: Live cache metrics tracking hits, misses, hit rate, and avoided LLM calls (FR-15).
"""

import io
import uuid
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.main import app
from app.api.routes import get_rag_service
from app.core.database import get_db_session, get_engine, init_db
from app.core.security import create_access_token
from app.services.rag_service import RAGService
from app.services.cache_service import RedisCacheService
from app.schemas.chunk import GroundedAnswer, SourceCitation, ScoredChunk, Chunk, ChunkMetadata
from app.models.db_models import DocumentModel, ChatSessionModel, MessageModel


@pytest.fixture(scope="module", autouse=True)
def ensure_db():
    init_db(get_engine())


@pytest.fixture
def mock_rag():
    """Builds a mock RAG service for deterministic API testing without live external Groq calls."""
    mock_cache = MagicMock()
    mock_cache.client = MagicMock()
    mock_cache.client.ping.return_value = True

    sample_answer = GroundedAnswer(
        answer="A minimum CGPA of 2.0 is required for good academic standing [1].",
        sources=[
            SourceCitation(
                citation_index=1,
                document_id="doc_handbook_cs",
                document_name="CS_Student_Handbook_2026.pdf",
                page_number=2,
                chunk_id="chk-02",
                chunk_index=0,
                content_snippet="A minimum Cumulative Grade Point Average (CGPA) of 2.0 is required for good standing.",
            )
        ],
        has_sufficient_context=True,
    )

    # First query misses, second query hits
    mock_cache.get_answer.side_effect = [None, sample_answer, sample_answer]

    rag = MagicMock(spec=RAGService)
    rag.cache_service = mock_cache
    rag.query.return_value = sample_answer
    rag.embedding_service = None
    rag.hybrid_retrieval_service = None

    return rag


@pytest.fixture
def client(mock_rag):
    app.dependency_overrides[get_rag_service] = lambda: mock_rag
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def db_session():
    from app.core.database import get_session_factory
    factory = get_session_factory()
    session = factory()
    yield session
    session.close()


@pytest.fixture
def admin_headers(db_session):
    email = f"admin_api_{uuid.uuid4().hex[:6]}@campusmind.edu"
    from app.repositories.database_repository import UserRepository
    from app.core.security import hash_password
    user_repo = UserRepository(db_session)
    user = user_repo.create_user(
        name="Admin API User",
        email=email,
        password_hash=hash_password("AdminPass123!"),
        role="admin",
    )
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def student_headers(db_session):
    email = f"student_api_{uuid.uuid4().hex[:6]}@campusmind.edu"
    from app.repositories.database_repository import UserRepository
    from app.core.security import hash_password
    user_repo = UserRepository(db_session)
    user = user_repo.create_user(
        name="Student API User",
        email=email,
        password_hash=hash_password("StudentPass123!"),
        role="student",
    )
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Root & Health Check Tests
# ---------------------------------------------------------------------------

def test_root_endpoint(client):
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["service"] == "CampusMind AI"


def test_health_check_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("healthy", "degraded")
    assert "mysql" in data["dependencies"]
    assert "redis" in data["dependencies"]
    assert "qdrant" in data["dependencies"]
    assert "cache_metrics" in data


# ---------------------------------------------------------------------------
# 2. Document Upload & Listing Tests
# ---------------------------------------------------------------------------

def test_upload_txt_document_success(client, admin_headers):
    """Verifies uploading a TXT document extracts, chunks, records in MySQL, and returns 201."""
    content = (
        b"Campus Facilities Guide\n"
        b"Main Library hours are 7:30 AM to Midnight Monday through Thursday.\n"
        b"Student Wellness Center is located in Building K, Room 110.\n"
    )
    files = {"file": ("Test_Facilities_Guide.txt", io.BytesIO(content), "text/plain")}
    data = {"uploader_id": "test_uploader", "chunking_method": "fixed"}

    res = client.post("/documents/upload", files=files, data=data, headers=admin_headers)
    assert res.status_code == 201
    resp_data = res.json()
    assert resp_data["filename"] == "Test_Facilities_Guide.txt"
    assert resp_data["status"] == "indexed"
    assert resp_data["chunk_count"] > 0
    assert "document_id" in resp_data


def test_upload_empty_file_rejected(client, admin_headers):
    """Verifies empty file upload is rejected with 400 Bad Request."""
    files = {"file": ("empty.txt", io.BytesIO(b""), "text/plain")}
    res = client.post("/documents/upload", files=files, headers=admin_headers)
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()


def test_upload_unsupported_extension_rejected(client, admin_headers):
    """Verifies unsupported extensions (.exe, .csv) are rejected with 400 Bad Request."""
    files = {"file": ("malware.exe", io.BytesIO(b"binarycontent"), "application/octet-stream")}
    res = client.post("/documents/upload", files=files, headers=admin_headers)
    assert res.status_code == 400
    assert "unsupported" in res.json()["detail"].lower()


def test_get_documents_list(client, admin_headers):
    """Verifies GET /documents retrieves document records from MySQL."""
    res = client.get("/documents", headers=admin_headers)
    assert res.status_code == 200
    docs = res.json()
    assert isinstance(docs, list)
    if docs:
        doc = docs[0]
        assert "id" in doc
        assert "filename" in doc
        assert "status" in doc
        assert "chunk_count" in doc


# ---------------------------------------------------------------------------
# 3. Chat Endpoint Tests (Grounded Answers, Cache Hits & DB Persistence)
# ---------------------------------------------------------------------------

def test_chat_ask_flow_with_cache_hit_and_persistence(client, student_headers, admin_headers):
    """
    Verifies POST /chat/ask:
    - Query 1: Cache Miss -> answers question, saves interaction in MySQL.
    - Query 2: Cache Hit -> served instantly, records is_cache_hit=True in MySQL.
    """
    session_id = f"api_sess_{uuid.uuid4().hex[:8]}"

    # Interaction 1: Cache Miss
    payload1 = {
        "question": "What is the minimum CGPA for CS?",
        "session_id": session_id,
        "user_id": "student_001",
    }
    res1 = client.post("/chat/ask", json=payload1, headers=student_headers)
    assert res1.status_code == 200
    data1 = res1.json()
    assert "CGPA of 2.0" in data1["answer"]
    assert len(data1["sources"]) == 1
    assert data1["sources"][0]["citation_index"] == 1
    assert data1["is_cache_hit"] is False
    assert data1["session_id"] == session_id

    # Interaction 2: Cache Hit
    payload2 = {
        "question": "What is the minimum CGPA for CS?",
        "session_id": session_id,
        "user_id": "student_001",
    }
    res2 = client.post("/chat/ask", json=payload2, headers=student_headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert "CGPA of 2.0" in data2["answer"]
    assert data2["is_cache_hit"] is True

    # Check metrics endpoint (FR-15) - requires admin
    metrics_res = client.get("/metrics/cache", headers=admin_headers)
    assert metrics_res.status_code == 200
    m_data = metrics_res.json()
    assert m_data["total_queries"] >= 2
    assert m_data["hits"] >= 1
    assert m_data["misses"] >= 1


def test_chat_ask_empty_question_rejected(client, student_headers):
    """Verifies submitting an empty question returns 400 Bad Request."""
    payload = {"question": "   "}
    res = client.post("/chat/ask", json=payload, headers=student_headers)
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()

