"""
CampusMind AI - API Schemas
Defines request and response Pydantic models for FastAPI endpoints:
- Document upload and listing
- Chat question and answers
- Health and metrics
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, EmailStr, ConfigDict


# ---------------------------------------------------------------------------
# Authentication Schemas
# ---------------------------------------------------------------------------

# Payload for POST /auth/register.
class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=128, description="Full name of user")
    email: str = Field(..., description="Email address")
    password: str = Field(..., min_length=6, description="Plaintext password")
    role: Optional[str] = Field("student", description="Role (defaults to 'student'; 'admin' cannot be self-assigned)")


# Payload for POST /auth/login.
class UserLoginRequest(BaseModel):
    email: str = Field(..., description="Registered email address")
    password: str = Field(..., description="Plaintext password")


# Safe user profile representation without password hash.
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    role: str
    created_at: datetime


# JWT response after successful login or registration.
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None
    user: UserResponse


# Payload for POST /auth/refresh.
class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Active refresh token string")


# Payload for POST /auth/logout.
class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = Field(None, description="Active refresh token to revoke")


# ---------------------------------------------------------------------------
# Document Schemas
# ---------------------------------------------------------------------------

# Document record representation returned from GET /documents.
class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    file_path: Optional[str] = None
    uploader_id: Optional[str] = None
    upload_date: datetime
    status: str
    chunk_count: int
    version: str
    created_at: datetime
    updated_at: datetime


# Response returned from POST /documents/upload.
class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    chunk_count: int
    version: str
    message: str = "Document successfully extracted, chunked, embedded, and indexed."


# ---------------------------------------------------------------------------
# Chat Schemas
# ---------------------------------------------------------------------------

# Request payload for POST /chat/ask.
class ChatAskRequest(BaseModel):
    question: str = Field(..., description="User question to be answered by the RAG pipeline.")
    session_id: Optional[str] = Field(None, description="Optional existing chat session ID.")
    user_id: Optional[str] = Field(None, description="Optional user identifier.")
    scope: str = Field("public", description="Access scope tier (default: 'public').")
    filter_document_id: Optional[str] = Field(None, description="Optional document filter.")
    top_k: int = Field(5, description="Number of evidence chunks to retrieve and fuse.")


# Structured evidence citation reference.
class SourceCitationResponse(BaseModel):
    citation_index: int
    document_id: str
    document_name: str
    page_number: Optional[int] = None
    chunk_id: str
    chunk_index: int
    content_snippet: str


# Response returned from POST /chat/ask.
class ChatAskResponse(BaseModel):
    session_id: str
    message_id: str
    answer: str
    sources: List[SourceCitationResponse] = Field(default_factory=list)
    has_sufficient_context: bool
    is_cache_hit: bool


# ---------------------------------------------------------------------------
# Health and Metrics Schemas (FR-15)
# ---------------------------------------------------------------------------

# Status indicator for an external dependency.
class DependencyStatus(BaseModel):
    status: str  # 'healthy', 'degraded', 'unavailable'
    details: Optional[str] = None


# Live cache statistics and eviction configuration per SRS FR-15.
class CacheMetrics(BaseModel):
    hits: int = 0
    misses: int = 0
    total_queries: int = 0
    hit_rate_pct: float = 0.0
    llm_calls_avoided: int = 0
    ttl_seconds: int = 1800
    used_memory_human: str = "N/A"
    maxmemory_human: str = "N/A"
    configured_policy: str = "allkeys-lru"
    live_policy: str = "allkeys-lru"


# Request to switch active Redis eviction policy.
class CachePolicyUpdateRequest(BaseModel):
    policy: str = Field(..., description="Eviction policy: 'allkeys-lru' or 'allkeys-lfu'")
    maxmemory: Optional[str] = Field(None, description="Optional memory limit override, e.g. '100mb'")


# Application health and dependency status.
class HealthResponse(BaseModel):
    status: str
    app_env: str
    dependencies: Dict[str, DependencyStatus]
    cache_metrics: Optional[CacheMetrics] = None

