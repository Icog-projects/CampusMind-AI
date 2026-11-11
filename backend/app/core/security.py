"""CampusMind AI - Authentication & Cryptography Utilities.

Handles password hashing (bcrypt), JSON Web Token (JWT) encoding and decoding, and refresh token generation.

Responsibilities:
1. get_jwt_secret(): Retrieves JWT secret key from environment or fallback default.
2. get_jwt_algorithm(): Retrieves the configured cryptographic signing algorithm.
3. get_token_expire_minutes(): Returns JWT access token expiration duration in minutes.
4. get_refresh_token_expire_days(): Returns refresh token expiration duration in days.
5. hash_password(): Generates a secure salted bcrypt hash for a plaintext password.
6. verify_password(): Verifies whether a candidate plaintext password matches a stored bcrypt hash.
7. create_access_token(): Signs and encodes a JWT token with subject ID, role, and expiration timestamp.
8. decode_access_token(): Decodes and verifies the cryptographic signature of a JWT string.
9. generate_refresh_token(): Generates a cryptographically secure random refresh token string.
10. hash_token(): Computes SHA-256 hash of a raw token string for secure persistent storage.
"""

import os
import hashlib
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import bcrypt
import jwt

logger = logging.getLogger(__name__)

DEFAULT_JWT_ALGORITHM = "HS256"
DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 60
DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS = 30


# Reads the JWT signing secret from environment variables.
def get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        # Fallback to deterministic development secret if not explicitly provided
        secret = "campusmind-dev-jwt-secret-key-change-in-production-2026"
    return secret


def get_jwt_algorithm() -> str:
    return os.getenv("JWT_ALGORITHM", DEFAULT_JWT_ALGORITHM)


def get_token_expire_minutes() -> int:
    exp_str = os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", str(DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES))
    try:
        return int(exp_str)
    except ValueError:
        return DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES


def get_refresh_token_expire_days() -> int:
    exp_str = os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", str(DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS))
    try:
        return int(exp_str)
    except ValueError:
        return DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS


# ---------------------------------------------------------------------------
# Password Hashing Functions
# ---------------------------------------------------------------------------

# Hashes a plaintext password using bcrypt with automatic salt generation.
def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty.")
    # bcrypt requires bytes
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


# Verifies a plaintext password against a stored bcrypt hash.
def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception as e:
        logger.warning("Password verification failure: %s", e)
        return False


# ---------------------------------------------------------------------------
# JWT Token Functions
# ---------------------------------------------------------------------------

# Creates a signed JWT access token containing subject (user_id), email, role, and expiration timestamp.
def create_access_token(
    user_id: str,
    email: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=get_token_expire_minutes())

    payload = {
        "sub": str(user_id),
        "email": email.strip().lower(),
        "role": role.strip().lower(),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    if extra_claims:
        payload.update(extra_claims)

    secret = get_jwt_secret()
    algorithm = get_jwt_algorithm()

    token = jwt.encode(payload, secret, algorithm=algorithm)
    return token


# Decodes and validates a signed JWT token.
def decode_access_token(token: str) -> Dict[str, Any]:
    secret = get_jwt_secret()
    algorithm = get_jwt_algorithm()

    payload = jwt.decode(
        token,
        secret,
        algorithms=[algorithm],
        options={"require": ["sub", "role", "exp"]},
    )
    return payload


# Generates a cryptographically secure random refresh token string.
def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


# Computes SHA-256 hash of a raw token string for secure persistent storage.
def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()

