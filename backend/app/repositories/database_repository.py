"""
CampusMind AI - Relational Repositories
Encapsulates database access operations for:
1. DocumentRepository: CRUD for uploaded documents and status updates.
2. ChatRepository: CRUD for chat sessions and messages with cache-hit indicator recording.
"""

import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.db_models import UserModel, DocumentModel, ChatSessionModel, MessageModel, utc_now


class UserRepository:
    """Repository handling CRUD operations for UserModel."""

    def __init__(self, session: Session):
        self.session = session

    def create_user(
        self,
        name: str,
        email: str,
        password_hash: str,
        role: str = "student",
        user_id: Optional[str] = None,
    ) -> UserModel:
        """Creates and stores a new user account."""
        uid = user_id or str(uuid.uuid4())
        user = UserModel(
            id=uid,
            name=name.strip(),
            email=email.strip().lower(),
            password_hash=password_hash,
            role=role.strip().lower(),
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def get_by_id(self, user_id: str) -> Optional[UserModel]:
        """Fetches a user by primary key."""
        return self.session.query(UserModel).filter(UserModel.id == user_id).first()

    def get_by_email(self, email: str) -> Optional[UserModel]:
        """Fetches a user by unique lowercase email."""
        if not email:
            return None
        return self.session.query(UserModel).filter(UserModel.email == email.strip().lower()).first()

    def list_users(self, role: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[UserModel]:
        """Lists users with optional role filtering."""
        query = self.session.query(UserModel)
        if role:
            query = query.filter(UserModel.role == role.strip().lower())
        return query.order_by(desc(UserModel.created_at)).offset(offset).limit(limit).all()


class DocumentRepository:
    """Repository handling CRUD operations for DocumentModel."""

    def __init__(self, session: Session):
        self.session = session

    def create_document(
        self,
        document_id: str,
        filename: str,
        file_path: Optional[str] = None,
        uploader_id: Optional[str] = None,
        status: str = "uploaded",
        chunk_count: int = 0,
        version: str = "v1",
    ) -> DocumentModel:
        """Creates and stores a new document record."""
        doc = DocumentModel(
            id=document_id,
            filename=filename,
            file_path=file_path,
            uploader_id=uploader_id,
            status=status,
            chunk_count=chunk_count,
            version=version,
        )
        self.session.add(doc)
        self.session.commit()
        self.session.refresh(doc)
        return doc

    def get_by_id(self, document_id: str) -> Optional[DocumentModel]:
        """Fetches a document by primary key."""
        return self.session.query(DocumentModel).filter(DocumentModel.id == document_id).first()

    def list_documents(
        self,
        status: Optional[str] = None,
        version: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[DocumentModel]:
        """Lists documents with optional status and version filtering."""
        query = self.session.query(DocumentModel)
        if status:
            query = query.filter(DocumentModel.status == status)
        if version:
            query = query.filter(DocumentModel.version == version)
        return query.order_by(desc(DocumentModel.upload_date)).offset(offset).limit(limit).all()

    def update_status(
        self,
        document_id: str,
        status: str,
        chunk_count: Optional[int] = None,
        version: Optional[str] = None,
    ) -> Optional[DocumentModel]:
        """Updates document status, chunk count, and version."""
        doc = self.get_by_id(document_id)
        if not doc:
            return None
        doc.status = status
        if chunk_count is not None:
            doc.chunk_count = chunk_count
        if version is not None:
            doc.version = version
        doc.updated_at = utc_now()
        self.session.commit()
        self.session.refresh(doc)
        return doc

    def delete_document(self, document_id: str) -> bool:
        """Deletes a document record by ID."""
        doc = self.get_by_id(document_id)
        if not doc:
            return False
        self.session.delete(doc)
        self.session.commit()
        return True


class ChatRepository:
    """Repository handling CRUD operations for ChatSessionModel and MessageModel."""

    def __init__(self, session: Session):
        self.session = session

    def create_session(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        title: str = "New Conversation",
    ) -> ChatSessionModel:
        """Creates and stores a new conversation session."""
        sid = session_id or str(uuid.uuid4())
        chat_session = ChatSessionModel(
            id=sid,
            user_id=user_id,
            title=title,
        )
        self.session.add(chat_session)
        self.session.commit()
        self.session.refresh(chat_session)
        return chat_session

    def get_session(self, session_id: str) -> Optional[ChatSessionModel]:
        """Fetches a session by primary key."""
        return self.session.query(ChatSessionModel).filter(ChatSessionModel.id == session_id).first()

    def list_sessions_for_user(
        self,
        user_id: Optional[str],
        limit: int = 50,
        offset: int = 0,
    ) -> List[ChatSessionModel]:
        """Lists chat sessions belonging to a specific user or anonymous user."""
        query = self.session.query(ChatSessionModel)
        if user_id:
            query = query.filter(ChatSessionModel.user_id == user_id)
        return query.order_by(desc(ChatSessionModel.created_at)).offset(offset).limit(limit).all()

    def create_message(
        self,
        session_id: str,
        role: str,
        content: str,
        source_references: Optional[List[Dict[str, Any]]] = None,
        is_cache_hit: bool = False,
        message_id: Optional[str] = None,
    ) -> MessageModel:
        """
        Stores a message within a session, including role, content,
        structured source citations, and cache-hit status (SRS Section 8.1, 9.1).
        """
        msg = MessageModel(
            id=message_id or str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            source_references=source_references,
            is_cache_hit=is_cache_hit,
        )
        self.session.add(msg)
        self.session.commit()
        self.session.refresh(msg)
        return msg

    def get_session_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[MessageModel]:
        """Retrieves messages for a session in chronological order."""
        return (
            self.session.query(MessageModel)
            .filter(MessageModel.session_id == session_id)
            .order_by(MessageModel.created_at.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def delete_session(self, session_id: str) -> bool:
        """Deletes a chat session and cascades deletion of its messages."""
        session_obj = self.get_session(session_id)
        if not session_obj:
            return False
        self.session.delete(session_obj)
        self.session.commit()
        return True

