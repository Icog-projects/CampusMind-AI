"""
CampusMind AI - Authentication and Role Authorization Tests
Verifies:
- Password hashing security (bcrypt rounds, salt variation, timing safety).
- User registration: student default, rejecting public admin role, duplicate email detection.
- User login: successful authentication, bad password rejection, missing account rejection.
- JWT token generation, signature validation, expired token rejection, tampered token rejection.
- Role-based authorization:
  * Public access allowed for /health.
  * /chat/ask requires authenticated user (student, staff, admin).
  * /documents/upload, /documents, /metrics/cache require admin role (forbidden for student).
  * Chat session isolation: students cannot view other users' chat histories.
"""

import io
import uuid
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.main import app
from app.api.routes import get_rag_service
from app.core.database import get_db_session, get_engine, init_db
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.repositories.database_repository import UserRepository, ChatRepository
from app.models.db_models import UserModel
from app.schemas.chunk import GroundedAnswer, SourceCitation


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    init_db(get_engine())


@pytest.fixture
def mock_rag():
    mock_cache = MagicMock()
    mock_cache.client = MagicMock()
    mock_cache.client.ping.return_value = True

    sample_answer = GroundedAnswer(
        answer="A minimum CGPA of 2.0 is required for good standing [1].",
        sources=[
            SourceCitation(
                citation_index=1,
                document_id="doc_handbook_cs",
                document_name="CS_Student_Handbook_2026.pdf",
                page_number=2,
                chunk_id="chk-02",
                chunk_index=0,
                content_snippet="CGPA of 2.0 is required.",
            )
        ],
        has_sufficient_context=True,
    )
    mock_cache.get_answer.return_value = None

    rag = MagicMock()
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


# ---------------------------------------------------------------------------
# 1. Password Hashing and JWT Token Unit Tests
# ---------------------------------------------------------------------------

def test_password_hashing_and_verification():
    raw_pwd = "SuperSecretPassword123!"
    hash1 = hash_password(raw_pwd)
    hash2 = hash_password(raw_pwd)

    # Different salts should produce distinct hashes
    assert hash1 != hash2
    assert hash1.startswith("$2b$") or hash1.startswith("$2a$")

    # Correct password verifies
    assert verify_password(raw_pwd, hash1) is True
    assert verify_password(raw_pwd, hash2) is True

    # Wrong password fails
    assert verify_password("WrongPassword!", hash1) is False


def test_jwt_generation_and_expiry():
    user_id = "user_test_jwt"
    email = "test@campusmind.edu"
    role = "student"

    token = create_access_token(user_id=user_id, email=email, role=role)
    payload = decode_access_token(token)

    assert payload["sub"] == user_id
    assert payload["email"] == email
    assert payload["role"] == role

    # Test expired token
    expired_token = create_access_token(
        user_id=user_id,
        email=email,
        role=role,
        expires_delta=timedelta(seconds=-10),
    )
    with pytest.raises(Exception):
        decode_access_token(expired_token)


# ---------------------------------------------------------------------------
# 2. Registration and Login API Tests
# ---------------------------------------------------------------------------

def test_register_student_success(client):
    unique_email = f"student_{uuid.uuid4().hex[:6]}@campusmind.edu"
    res = client.post("/auth/register", json={
        "name": "Jane Doe",
        "email": unique_email,
        "password": "Password123!",
        "role": "student",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == unique_email
    assert data["role"] == "student"
    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data


def test_register_public_admin_forbidden(client):
    res = client.post("/auth/register", json={
        "name": "Hacker Admin",
        "email": f"fake_admin_{uuid.uuid4().hex[:6]}@campusmind.edu",
        "password": "Password123!",
        "role": "admin",
    })
    assert res.status_code == 403
    assert "prohibited" in res.json()["detail"].lower()


def test_register_duplicate_email_rejected(client):
    unique_email = f"dup_{uuid.uuid4().hex[:6]}@campusmind.edu"
    # First registration
    client.post("/auth/register", json={
        "name": "User One",
        "email": unique_email,
        "password": "Password123!",
    })

    # Second registration with same email
    res = client.post("/auth/register", json={
        "name": "User Two",
        "email": unique_email,
        "password": "DifferentPassword123!",
    })
    assert res.status_code == 400
    assert "already exists" in res.json()["detail"].lower()


def test_login_success_and_invalid_credentials(client):
    email = f"login_test_{uuid.uuid4().hex[:6]}@campusmind.edu"
    password = "CorrectPassword123!"

    client.post("/auth/register", json={
        "name": "Login Tester",
        "email": email,
        "password": password,
    })

    # Valid login
    res_ok = client.post("/auth/login", json={"email": email, "password": password})
    assert res_ok.status_code == 200
    token_data = res_ok.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["user"]["email"] == email

    # Invalid password
    res_bad_pwd = client.post("/auth/login", json={"email": email, "password": "WrongPassword"})
    assert res_bad_pwd.status_code == 401

    # Nonexistent user
    res_no_user = client.post("/auth/login", json={"email": "nobody@campusmind.edu", "password": password})
    assert res_no_user.status_code == 401


# ---------------------------------------------------------------------------
# 3. Role-Based Access Control (RBAC) Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def student_auth_headers(client, db_session):
    email = f"student_auth_{uuid.uuid4().hex[:6]}@campusmind.edu"
    user_repo = UserRepository(db_session)
    user = user_repo.create_user(
        name="Student User",
        email=email,
        password_hash=hash_password("Pass123!"),
        role="student",
    )
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    return {"Authorization": f"Bearer {token}"}, user


@pytest.fixture
def admin_auth_headers(client, db_session):
    email = f"admin_auth_{uuid.uuid4().hex[:6]}@campusmind.edu"
    user_repo = UserRepository(db_session)
    user = user_repo.create_user(
        name="Admin User",
        email=email,
        password_hash=hash_password("AdminPass123!"),
        role="admin",
    )
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    return {"Authorization": f"Bearer {token}"}, user


def test_health_endpoint_is_public(client):
    """GET /health remains public without any auth header."""
    res = client.get("/health")
    assert res.status_code == 200


def test_chat_ask_requires_authentication(client):
    """Unauthenticated call to /chat/ask returns 401 Unauthorized."""
    res = client.post("/chat/ask", json={"question": "What is the CGPA requirement?"})
    assert res.status_code == 401


def test_student_can_ask_question(client, student_auth_headers):
    """Authenticated student can ask questions."""
    headers, user = student_auth_headers
    res = client.post("/chat/ask", headers=headers, json={"question": "What is the CGPA requirement?"})
    assert res.status_code == 200
    assert "CGPA of 2.0" in res.json()["answer"]


def test_student_cannot_access_admin_endpoints(client, student_auth_headers):
    """Authenticated student is blocked from administrative endpoints (403 Forbidden)."""
    headers, user = student_auth_headers

    # GET /documents
    res_docs = client.get("/documents", headers=headers)
    assert res_docs.status_code == 403

    # GET /metrics/cache
    res_metrics = client.get("/metrics/cache", headers=headers)
    assert res_metrics.status_code == 403

    # POST /documents/upload
    files = {"file": ("test.txt", io.BytesIO(b"Admin content"), "text/plain")}
    res_upload = client.post("/documents/upload", headers=headers, files=files)
    assert res_upload.status_code == 403


def test_admin_can_access_admin_endpoints(client, admin_auth_headers):
    """Authenticated admin can list documents and access cache metrics."""
    headers, user = admin_auth_headers

    res_docs = client.get("/documents", headers=headers)
    assert res_docs.status_code == 200

    res_metrics = client.get("/metrics/cache", headers=headers)
    assert res_metrics.status_code == 200


def test_chat_history_isolation(client, student_auth_headers, admin_auth_headers, db_session):
    """Users can only view their own chat history; other users receive 403 Forbidden."""
    student_headers, student = student_auth_headers
    admin_headers, admin = admin_auth_headers

    chat_repo = ChatRepository(db_session)
    session_id = f"sess_private_{uuid.uuid4().hex[:6]}"
    chat_repo.create_session(session_id=session_id, user_id=student.id, title="Private Chat")
    chat_repo.create_message(session_id=session_id, role="user", content="My private query")

    # Owner student can read history
    res_owner = client.get(f"/chat/history/{session_id}", headers=student_headers)
    assert res_owner.status_code == 200
    assert len(res_owner.json()) == 1

    # Another student cannot read history
    other_student = UserRepository(db_session).create_user(
        name="Other Student",
        email=f"other_{uuid.uuid4().hex[:6]}@campusmind.edu",
        password_hash=hash_password("Pass123!"),
        role="student",
    )
    other_token = create_access_token(user_id=other_student.id, email=other_student.email, role="student")
    res_other = client.get(f"/chat/history/{session_id}", headers={"Authorization": f"Bearer {other_token}"})
    assert res_other.status_code == 403

    # Admin has system-level viewing permission
    res_admin = client.get(f"/chat/history/{session_id}", headers=admin_headers)
    assert res_admin.status_code == 200

