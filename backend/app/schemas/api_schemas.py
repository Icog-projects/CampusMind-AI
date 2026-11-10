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

class UserRegisterRequest(BaseModel):
    """Payload for POST /auth/register."""
    name: str = Field(..., min_length=2, max_length=128, description="Full name of user")
    email: str = Field(..., description="Email address")
    password: str = Field(..., min_length=6, description="Plaintext password")
    role: Optional[str] = Field("student", description="Role (defaults to 'student'; 'admin' cannot be self-assigned)")


class UserLoginRequest(BaseModel):
    """Payload for POST /auth/login."""
    email: str = Field(..., description="Registered email address")
    password: str = Field(..., description="Plaintext password")


class UserResponse(BaseModel):
    """Safe user profile representation without password hash."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    role: str
    created_at: datetime


class TokenResponse(BaseModel):
    """JWT response after successful login or registration."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ---------------------------------------------------------------------------
# Document Schemas
# ---------------------------------------------------------------------------

class DocumentResponse(BaseModel):
    """Document record representation returned from GET /documents."""
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


class DocumentUploadResponse(BaseModel):
    """Response returned from POST /documents/upload."""
    document_id: str
    filename: str
    status: str
    chunk_count: int
    version: str
    message: str = "Document successfully extracted, chunked, embedded, and indexed."


# ---------------------------------------------------------------------------
# Chat Schemas
# ---------------------------------------------------------------------------

class ChatAskRequest(BaseModel):
    """Request payload for POST /chat/ask."""
    question: str = Field(..., description="User question to be answered by the RAG pipeline.")
    session_id: Optional[str] = Field(None, description="Optional existing chat session ID.")
    user_id: Optional[str] = Field(None, description="Optional user identifier.")
    scope: str = Field("public", description="Access scope tier (default: 'public').")
    filter_document_id: Optional[str] = Field(None, description="Optional document filter.")
    top_k: int = Field(5, description="Number of evidence chunks to retrieve and fuse.")


class SourceCitationResponse(BaseModel):
    """Structured evidence citation reference."""
    citation_index: int
    document_id: str
    document_name: str
    page_number: Optional[int] = None
    chunk_id: str
    chunk_index: int
    content_snippet: str


class ChatAskResponse(BaseModel):
    """Response returned from POST /chat/ask."""
    session_id: str
    message_id: str
    answer: str
    sources: List[SourceCitationResponse] = Field(default_factory=list)
    has_sufficient_context: bool
    is_cache_hit: bool


# ---------------------------------------------------------------------------
# Health and Metrics Schemas (FR-15)
# ---------------------------------------------------------------------------

class DependencyStatus(BaseModel):
    """Status indicator for an external dependency."""
    status: str  # 'healthy', 'degraded', 'unavailable'
    details: Optional[str] = None


class CacheMetrics(BaseModel):
    """Live cache statistics per SRS FR-15."""
    hits: int = 0
    misses: int = 0
    total_queries: int = 0
    hit_rate_pct: float = 0.0
    llm_calls_avoided: int = 0


class HealthResponse(BaseModel):
    """Application health and dependency status."""
    status: str
    app_env: str
    dependencies: Dict[str, DependencyStatus]
    cache_metrics: Optional[CacheMetrics] = None

