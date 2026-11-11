"""CampusMind AI - Refresh Token & Session Renewal Unit Tests.

Validates:
1. Login returns short-lived access_token and long-lived refresh_token.
2. /auth/refresh returns a new valid access_token with matching user identity.
3. Expired access token fails authentication on protected endpoint (/auth/me).
4. Renewed access token succeeds on protected endpoint.
5. Invalid or tampered refresh token is rejected with HTTP 401.
6. Logout revokes the refresh token; subsequent renewal attempt fails.
7. Admin permissions, RBAC, and access scope are fully preserved across renewals.
"""

import uuid
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, hash_password
from app.models.db_models import UserModel
from app.repositories.database_repository import UserRepository, RefreshTokenRepository
from app.core.database import get_db_session, get_session_factory, get_engine, init_db

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    init_db(get_engine())


@pytest.fixture
def db_session():
    factory = get_session_factory()
    session = factory()
    yield session
    session.close()


@pytest.fixture
def auth_test_users(db_session):
    user_repo = UserRepository(db_session)
    admin_email = f"admin_renewal_{uuid.uuid4().hex[:6]}@campusmind.edu"
    student_email = f"student_renewal_{uuid.uuid4().hex[:6]}@campusmind.edu"

    admin_user = user_repo.create_user(
        name="Admin Renewal Test",
        email=admin_email,
        password_hash=hash_password("AdminPass123!"),
        role="admin",
    )
    student_user = user_repo.create_user(
        name="Student Renewal Test",
        email=student_email,
        password_hash=hash_password("StudentPass123!"),
        role="student",
    )
    return {
        "admin": admin_user,
        "admin_email": admin_email,
        "admin_pass": "AdminPass123!",
        "student": student_user,
        "student_email": student_email,
        "student_pass": "StudentPass123!",
    }


# Test login issues both access_token and refresh_token
def test_login_issues_access_and_refresh_tokens(auth_test_users):
    resp = client.post(
        "/auth/login",
        json={"email": auth_test_users["admin_email"], "password": auth_test_users["admin_pass"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert len(data["refresh_token"]) > 30
    assert data["user"]["role"] == "admin"


# Test /auth/refresh successfully renews access token
def test_refresh_token_endpoint_renews_access_token(auth_test_users):
    login_resp = client.post(
        "/auth/login",
        json={"email": auth_test_users["admin_email"], "password": auth_test_users["admin_pass"]},
    )
    r_token = login_resp.json()["refresh_token"]

    refresh_resp = client.post(
        "/auth/refresh",
        json={"refresh_token": r_token},
    )
    assert refresh_resp.status_code == 200
    data = refresh_resp.json()
    assert "access_token" in data
    assert data["user"]["role"] == "admin"

    # Verify new access token grants access to protected endpoint
    me_resp = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == auth_test_users["admin_email"]


# Test expired access token fails while renewal restores access
def test_expired_access_token_renewal_flow(auth_test_users):
    admin = auth_test_users["admin"]

    # Create an intentionally expired access token (1 second in the past)
    expired_token = create_access_token(
        user_id=admin.id,
        email=admin.email,
        role=admin.role,
        expires_delta=timedelta(seconds=-10),
    )

    # Request with expired access token must fail with 401
    fail_resp = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert fail_resp.status_code == 401
    assert "expired" in fail_resp.json().get("detail", "").lower()

    # Login to obtain valid refresh token
    login_resp = client.post(
        "/auth/login",
        json={"email": auth_test_users["admin_email"], "password": auth_test_users["admin_pass"]},
    )
    r_token = login_resp.json()["refresh_token"]

    # Renew access token using refresh token
    renew_resp = client.post(
        "/auth/refresh",
        json={"refresh_token": r_token},
    )
    assert renew_resp.status_code == 200
    new_access_token = renew_resp.json()["access_token"]

    # Verify access is restored with renewed access token
    ok_resp = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )
    assert ok_resp.status_code == 200
    assert ok_resp.json()["role"] == "admin"


# Test invalid or tampered refresh token is rejected
def test_invalid_refresh_token_rejected():
    resp = client.post(
        "/auth/refresh",
        json={"refresh_token": "invalid_bogus_token_1234567890"},
    )
    assert resp.status_code == 401
    assert "invalid" in resp.json().get("detail", "").lower()


# Test logout revokes refresh token
def test_logout_revokes_refresh_token(auth_test_users):
    login_resp = client.post(
        "/auth/login",
        json={"email": auth_test_users["admin_email"], "password": auth_test_users["admin_pass"]},
    )
    acc_token = login_resp.json()["access_token"]
    ref_token = login_resp.json()["refresh_token"]

    # Call /auth/logout
    logout_resp = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {acc_token}"},
        json={"refresh_token": ref_token},
    )
    assert logout_resp.status_code == 200

    # Subsequent refresh attempt must be rejected
    second_refresh = client.post(
        "/auth/refresh",
        json={"refresh_token": ref_token},
    )
    assert second_refresh.status_code == 401


# Test RBAC preservation for student and admin
def test_rbac_preserved_after_renewal(auth_test_users):
    # Student login & refresh
    s_login = client.post(
        "/auth/login",
        json={"email": auth_test_users["student_email"], "password": auth_test_users["student_pass"]},
    )
    s_refresh = client.post(
        "/auth/refresh",
        json={"refresh_token": s_login.json()["refresh_token"]},
    )
    s_acc = s_refresh.json()["access_token"]

    # Student cannot access admin-only /metrics/cache
    s_forbidden = client.get(
        "/metrics/cache",
        headers={"Authorization": f"Bearer {s_acc}"},
    )
    assert s_forbidden.status_code == 403

    # Admin login & refresh
    a_login = client.post(
        "/auth/login",
        json={"email": auth_test_users["admin_email"], "password": auth_test_users["admin_pass"]},
    )
    a_refresh = client.post(
        "/auth/refresh",
        json={"refresh_token": a_login.json()["refresh_token"]},
    )
    a_acc = a_refresh.json()["access_token"]

    # Admin can access admin-only /metrics/cache
    a_allowed = client.get(
        "/metrics/cache",
        headers={"Authorization": f"Bearer {a_acc}"},
    )
    assert a_allowed.status_code == 200
