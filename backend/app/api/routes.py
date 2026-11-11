
"""CampusMind AI - API Routers.

Implements FastAPI endpoints for authentication, documents, chat operations, and health telemetry.

Responsibilities:
1. get_rag_service(): Provides the singleton RAGService orchestrator instance.
2. register(): Handles user registration requests and hashes user passwords.
3. login(): Authenticates user credentials and issues signed JWT access and refresh tokens.
4. refresh_token(): Automatically renews expired access tokens using a valid refresh token.
5. logout(): Revokes user refresh token sessions on logout.
6. get_me(): Returns the authenticated user's profile details.
7. upload_document(): Ingests, chunks, embeds, and indexes an uploaded document.
8. list_documents(): Retrieves paginated document records from the database.
9. ask_question(): Processes chat questions through the grounded RAG pipeline.
10. list_chat_sessions(): Lists chat sessions owned by the authenticated user.
11. get_chat_history(): Returns stored message history for a specific conversation session.
12. health_check(): Reports operational status of MySQL, Redis, and Qdrant dependencies.
13. get_cache_metrics(): Computes cache hit/miss telemetry, avoided LLM inference, and memory stats.
14. update_cache_policy(): Switches active Redis eviction policy between allkeys-lru and allkeys-lfu.
"""

import os
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from datetime import datetime, timedelta, timezone
from app.core.database import get_db_session
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_refresh_token,
    hash_token,
    get_refresh_token_expire_days,
)
from app.core.auth import (
    get_current_user,
    require_admin,
    require_authenticated_user,
)
from app.models.db_models import UserModel, utc_now
from app.repositories.database_repository import (
    UserRepository,
    RefreshTokenRepository,
    DocumentRepository,
    ChatRepository,
)
from app.services.ingestion_service import IngestionService
from app.services.chat_service import ChatService
from app.services.rag_service import RAGService
from app.services.cache_service import RedisCacheService
from app.services.vector_store import VectorStoreService
from app.services.document_extractor import (
    UnsupportedFileTypeError,
    FileValidationError,
    DocumentExtractionError,
)
from app.schemas.api_schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
    RefreshTokenRequest,
    LogoutRequest,
    DocumentResponse,
    DocumentUploadResponse,
    ChatAskRequest,
    ChatAskResponse,
    HealthResponse,
    DependencyStatus,
    CacheMetrics,
    CachePolicyUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Global singletons for in-process shared services
_shared_rag_service: Optional[RAGService] = None

# In-memory session counters for FR-15 cache metrics
_cache_hits_counter: int = 0
_cache_misses_counter: int = 0


def get_rag_service() -> RAGService:
    global _shared_rag_service
    if _shared_rag_service is None:
        from app.services.embedding_service import EmbeddingService
        from app.services.vector_store import VectorStoreService
        from app.services.semantic_cache_service import SemanticCacheService
        from app.services.retrieval_bm25 import BM25RetrievalService
        from app.services.hybrid_retrieval import HybridRetrievalService
        from app.services.reranking_service import RerankingService
        from app.services.generation_service import GenerationService

        embed_svc = EmbeddingService()
        vec_store = VectorStoreService()
        semantic_cache_svc = SemanticCacheService(qdrant_client=vec_store.client)
        bm25_svc = BM25RetrievalService()
        hybrid_svc = HybridRetrievalService(bm25_service=bm25_svc, vector_store=vec_store)
        rerank_svc = RerankingService()
        gen_svc = GenerationService()

        _shared_rag_service = RAGService(
            embedding_service=embed_svc,
            semantic_cache_service=semantic_cache_svc,
            hybrid_retrieval_service=hybrid_svc,
            reranking_service=rerank_svc,
            generation_service=gen_svc,
        )
    return _shared_rag_service


# ---------------------------------------------------------------------------
# 1. Authentication Endpoints (SRS v1.2, Section 3.1 & 8.1)
# ---------------------------------------------------------------------------

@router.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account (Student or Staff)",
    tags=["Authentication"],
)
# Registers a new account.
def register(
    req: UserRegisterRequest,
    db: Session = Depends(get_db_session),
):
    user_repo = UserRepository(db)

    # 1. Check for existing email
    existing_user = user_repo.get_by_email(req.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An account with email '{req.email.strip().lower()}' already exists.",
        )

    # 2. Prevent unauthorized self-assignment of admin role
    clean_role = (req.role or "student").strip().lower()
    if clean_role == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration as admin is prohibited. Admin accounts must be created through a controlled process.",
        )
    if clean_role not in ("student", "staff"):
        clean_role = "student"

    # 3. Hash password and persist user
    hashed_pwd = hash_password(req.password)
    user = user_repo.create_user(
        name=req.name,
        email=req.email,
        password_hash=hashed_pwd,
        role=clean_role,
    )

    logger.info("New user registered: %s (role: %s)", user.email, user.role)
    return user


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User login and JWT access token issuance",
    tags=["Authentication"],
)
# Authenticates user with email and password.
def login(
    req: UserLoginRequest,
    db: Session = Depends(get_db_session),
):
    user_repo = UserRepository(db)
    user = user_repo.get_by_email(req.email)

    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
    )

    # Issue long-lived secure refresh token persisted in MySQL
    raw_refresh_token = generate_refresh_token()
    token_hash = hash_token(raw_refresh_token)
    expire_days = get_refresh_token_expire_days()
    refresh_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=expire_days)

    refresh_repo = RefreshTokenRepository(db)
    refresh_repo.create_token(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=refresh_expires_at,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        refresh_token=raw_refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Renew expired access token using valid refresh token",
    tags=["Authentication"],
)
# Automatically renews expired access tokens using a valid refresh token.
def refresh_token(
    req: RefreshTokenRequest,
    db: Session = Depends(get_db_session),
):
    refresh_repo = RefreshTokenRepository(db)
    token_hash = hash_token(req.refresh_token)
    token_record = refresh_repo.get_valid_token(token_hash)

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or revoked refresh token. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_repo = UserRepository(db)
    user = user_repo.get_by_id(token_record.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with refresh token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Issue renewed short-lived access token
    new_access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
    )

    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        refresh_token=req.refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/auth/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout user and invalidate refresh token session",
    tags=["Authentication"],
)
# Revokes user refresh token sessions on logout.
def logout(
    req: Optional[LogoutRequest] = None,
    current_user: Optional[UserModel] = Depends(require_authenticated_user),
    db: Session = Depends(get_db_session),
):
    refresh_repo = RefreshTokenRepository(db)
    if req and req.refresh_token:
        refresh_repo.revoke_token(hash_token(req.refresh_token))
    elif current_user:
        refresh_repo.revoke_all_for_user(current_user.id)

    return {"message": "Session logged out and refresh token revoked successfully."}


@router.get(
    "/auth/me",
    response_model=UserResponse,
    summary="Get current user profile",
    tags=["Authentication"],
)
# Returns the authenticated user's profile.
def get_me(
    current_user: UserModel = Depends(require_authenticated_user),
):
    return current_user


# ---------------------------------------------------------------------------
# 2. Document Endpoints (Role: Admin only per SRS v1.2 Section 2)
# ---------------------------------------------------------------------------

@router.post(
    "/documents/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a document (PDF, DOCX, TXT) [Admin Only]",
    tags=["Documents"],
)
async def upload_document(
    file: UploadFile = File(..., description="Document file (.pdf, .docx, or .txt)"),
    uploader_id: Optional[str] = Form(None),
    chunking_method: str = Form("recursive"),
    chunk_size_tokens: Optional[int] = Form(None),
    chunk_overlap_tokens: Optional[int] = Form(None),
    current_user: UserModel = Depends(require_admin),
    db: Session = Depends(get_db_session),
    rag: RAGService = Depends(get_rag_service),
):
    """
    Admin-only endpoint to upload, chunk, embed, index documents,
    and invalidate the Redis cache.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a valid filename.",
        )

    try:
        content_bytes = await file.read()
        if len(content_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        ingestion = IngestionService(
            db_session=db,
            embedding_service=rag.embedding_service,
            vector_store_service=rag.hybrid_retrieval_service.vector_store if rag.hybrid_retrieval_service else None,
            bm25_service=rag.hybrid_retrieval_service.bm25_service if rag.hybrid_retrieval_service else None,
            cache_service=rag.cache_service,
        )

        result = ingestion.ingest_file(
            file_bytes=content_bytes,
            filename=file.filename,
            uploader_id=uploader_id or current_user.id,
            chunking_method=chunking_method,
            chunk_size_tokens=chunk_size_tokens,
            chunk_overlap_tokens=chunk_overlap_tokens,
        )

        return DocumentUploadResponse(
            document_id=result["document_id"],
            filename=result["filename"],
            status=result["status"],
            chunk_count=result["chunk_count"],
            version=result["version"],
            message="Document successfully processed and indexed into CampusMind AI.",
        )

    except (UnsupportedFileTypeError, FileValidationError) as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except DocumentExtractionError as ext_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Extraction failure: {str(ext_err)}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unhandled upload error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the document.",
        )


@router.get(
    "/documents",
    response_model=List[DocumentResponse],
    summary="List processed documents [Admin Only]",
    tags=["Documents"],
)
# Retrieves document records from MySQL (Admin only).
def list_documents(
    status_filter: Optional[str] = None,
    version: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: UserModel = Depends(require_admin),
    db: Session = Depends(get_db_session),
):
    repo = DocumentRepository(db)
    docs = repo.list_documents(
        status=status_filter,
        version=version,
        limit=limit,
        offset=offset,
    )
    return docs


# ---------------------------------------------------------------------------
# 3. Chat Endpoints (Protected: Authenticated Users)
# ---------------------------------------------------------------------------

@router.post(
    "/chat/ask",
    response_model=ChatAskResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit a query and receive a grounded answer with citations [Authenticated]",
    tags=["Chat"],
)
# Submits a user question to CampusMind AI.
def ask_question(
    req: ChatAskRequest,
    current_user: UserModel = Depends(require_authenticated_user),
    db: Session = Depends(get_db_session),
    rag: RAGService = Depends(get_rag_service),
):
    global _cache_hits_counter, _cache_misses_counter

    if not req.question or not req.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty.",
        )

    chat_repo = ChatRepository(db)

    # Verify session ownership if existing session_id supplied
    if req.session_id:
        existing_sess = chat_repo.get_session(req.session_id)
        if existing_sess and existing_sess.user_id and existing_sess.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access or append to this conversation session.",
            )

    # Set access scope according to user role to prevent unauthorized data cross-talk
    applicable_scope = req.scope
    if current_user.role == "student" and req.scope != "public":
        # Students are constrained to public documents
        applicable_scope = "public"

    chat_service = ChatService(db_session=db, rag_service=rag)

    try:
        result = chat_service.ask(
            question=req.question,
            session_id=req.session_id,
            user_id=current_user.id,
            scope=applicable_scope,
            filter_document_id=req.filter_document_id,
            top_k=req.top_k,
        )

        # Track runtime cache metrics (FR-15)
        if result["is_cache_hit"]:
            _cache_hits_counter += 1
        else:
            _cache_misses_counter += 1

        return ChatAskResponse(
            session_id=result["session_id"],
            message_id=result["message_id"],
            answer=result["answer"],
            sources=result["sources"],
            has_sufficient_context=result["has_sufficient_context"],
            is_cache_hit=result["is_cache_hit"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in ask_question endpoint: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate answer for the submitted query.",
        )


@router.get(
    "/chat/sessions",
    summary="List chat sessions for the authenticated user [Authenticated]",
    tags=["Chat"],
)
# Lists conversation sessions belonging to the current user.
def list_chat_sessions(
    current_user: UserModel = Depends(require_authenticated_user),
    db: Session = Depends(get_db_session),
):
    chat_repo = ChatRepository(db)
    sessions = chat_repo.list_sessions_for_user(current_user.id)
    return [
        {
            "id": s.id,
            "title": s.title,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
        }
        for s in sessions
    ]


@router.get(
    "/chat/history/{session_id}",
    summary="Retrieve chat messages for a session [Authenticated]",
    tags=["Chat"],
)
# Retrieves chronological messages for a chat session.
def get_chat_history(
    session_id: str,
    current_user: UserModel = Depends(require_authenticated_user),
    db: Session = Depends(get_db_session),
):
    chat_repo = ChatRepository(db)
    session_obj = chat_repo.get_session(session_id)
    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found.",
        )

    if session_obj.user_id and session_obj.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this chat session.",
        )

    messages = chat_repo.get_session_messages(session_id)
    return [
        {
            "id": m.id,
            "session_id": m.session_id,
            "role": m.role,
            "content": m.content,
            "source_references": m.source_references,
            "is_cache_hit": m.is_cache_hit,
            "created_at": m.created_at,
        }
        for m in messages
    ]


# ---------------------------------------------------------------------------
# 4. Health and Metrics Endpoints (FR-15)
# ---------------------------------------------------------------------------

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Application health check and dependency status (Public)",
    tags=["System"],
)
# Checks operational status of MySQL, Redis, and Qdrant dependencies.
def health_check(
    db: Session = Depends(get_db_session),
    rag: RAGService = Depends(get_rag_service),
):
    dependencies: dict[str, DependencyStatus] = {}

    # 1. MySQL Health
    try:
        db.execute(text("SELECT 1;"))
        dependencies["mysql"] = DependencyStatus(status="healthy", details="Connected to MySQL database")
    except Exception as e:
        dependencies["mysql"] = DependencyStatus(status="unavailable", details=str(e))

    # 2. Redis Health
    try:
        cli = rag.cache_service.client
        if cli is not None and cli.ping():
            dependencies["redis"] = DependencyStatus(status="healthy", details="Connected to Redis server")
        else:
            dependencies["redis"] = DependencyStatus(status="unavailable", details="Ping failed")
    except Exception as e:
        dependencies["redis"] = DependencyStatus(status="unavailable", details=str(e))

    # 3. Qdrant Health
    try:
        vs = rag.hybrid_retrieval_service.vector_store if rag.hybrid_retrieval_service else VectorStoreService()
        vs.client.get_collections()
        dependencies["qdrant"] = DependencyStatus(status="healthy", details="Qdrant service reachable")
    except Exception as e:
        dependencies["qdrant"] = DependencyStatus(status="degraded", details=str(e))

    # Calculate Cache Metrics (FR-15)
    total_queries = _cache_hits_counter + _cache_misses_counter
    hit_rate = round((_cache_hits_counter / total_queries * 100.0), 2) if total_queries > 0 else 0.0

    metrics = CacheMetrics(
        hits=_cache_hits_counter,
        misses=_cache_misses_counter,
        total_queries=total_queries,
        hit_rate_pct=hit_rate,
        llm_calls_avoided=_cache_hits_counter,
    )

    all_healthy = all(d.status == "healthy" for d in dependencies.values())
    overall_status = "healthy" if all_healthy else "degraded"

    return HealthResponse(
        status=overall_status,
        app_env="production" if False else "development",
        dependencies=dependencies,
        cache_metrics=metrics,
    )


@router.get(
    "/metrics/cache",
    response_model=CacheMetrics,
    summary="Live Redis cache metrics [Admin Only]",
    tags=["System"],
)
# Returns live cache metrics: hits, misses, hit rate, avoided LLM calls, and Redis eviction policy stats (Admin only).
def get_cache_metrics(
    current_user: UserModel = Depends(require_admin),
    rag: RAGService = Depends(get_rag_service),
):
    total_queries = _cache_hits_counter + _cache_misses_counter
    hit_rate = round((_cache_hits_counter / total_queries * 100.0), 2) if total_queries > 0 else 0.0

    info = rag.cache_service.get_cache_info() if hasattr(rag, "cache_service") and hasattr(rag.cache_service, "get_cache_info") else {}
    if not isinstance(info, dict):
        info = {}

    used_mem = info.get("used_memory_human")
    max_mem = info.get("maxmemory_human")
    cfg_policy = info.get("configured_policy")
    live_pol = info.get("live_policy")
    ttl = info.get("ttl_seconds")

    return CacheMetrics(
        hits=_cache_hits_counter,
        misses=_cache_misses_counter,
        total_queries=total_queries,
        hit_rate_pct=hit_rate,
        llm_calls_avoided=_cache_hits_counter,
        ttl_seconds=int(ttl) if isinstance(ttl, (int, float)) else 1800,
        used_memory_human=str(used_mem) if isinstance(used_mem, str) else "N/A",
        maxmemory_human=str(max_mem) if isinstance(max_mem, str) else "N/A",
        configured_policy=str(cfg_policy) if isinstance(cfg_policy, str) else "allkeys-lru",
        live_policy=str(live_pol) if isinstance(live_pol, str) else "allkeys-lru",
    )


@router.post(
    "/metrics/cache/policy",
    summary="Update Redis eviction policy (Admin Only)",
    tags=["System"],
)
# Switches the active Redis eviction policy between allkeys-lru and allkeys-lfu (Admin only).
def update_cache_policy(
    req: CachePolicyUpdateRequest,
    current_user: UserModel = Depends(require_admin),
    rag: RAGService = Depends(get_rag_service),
):
    clean_policy = req.policy.strip().lower()
    if clean_policy not in ["allkeys-lru", "allkeys-lfu"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supported policies are 'allkeys-lru' and 'allkeys-lfu'.",
        )

    success = rag.cache_service.configure_eviction_policy(
        policy=clean_policy,
        maxmemory=req.maxmemory,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update Redis eviction policy configuration.",
        )

    info = rag.cache_service.get_cache_info()
    return {
        "message": f"Successfully updated Redis eviction policy to {clean_policy}.",
        "policy": clean_policy,
        "maxmemory": info.get("maxmemory_human"),
        "live_policy": info.get("live_policy"),
    }
