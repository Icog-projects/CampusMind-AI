"""CampusMind AI - SQLAlchemy ORM Models.

Defines database models for users, documents, chat sessions, and messages.

Responsibilities:
1. utc_now(): Generates timezone-naive UTC datetime timestamps for database records.
Class UserModel:
2. UserModel.__repr__(): Formats string representation of user account models.
Class DocumentModel:
3. DocumentModel.__repr__(): Formats string representation of document models.
Class ChatSessionModel:
4. ChatSessionModel.__repr__(): Formats string representation of chat session models.
Class MessageModel:
5. MessageModel.__repr__(): Formats string representation of chat message models.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    JSON,
)
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import relationship

from app.core.database import Base


def utc_now():
    """Generates naive UTC datetime for MySQL DATETIME(6)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UserModel(Base):
    """
    Stores registered user accounts, passwords, and permission roles.
    SRS Version 1.2, Section 3.1 & 5.1:
        id, name, email, password_hash, role, created_at
    """
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    email = Column(String(191), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), default="student", nullable=False)  # student, staff, admin
    created_at = Column(DATETIME(fsp=6), default=utc_now, nullable=False)
    updated_at = Column(DATETIME(fsp=6), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_users_role", "role"),
    )

    def __repr__(self):
        return f"<UserModel(id='{self.id}', email='{self.email}', role='{self.role}')>"


class DocumentModel(Base):
    """
    Tracks ingested files, extraction state, chunk counts, and KB versions.
    SRS Section 9.1:
        id, filename, file_path, uploader_id if available, upload_date, status, chunk_count, version
    """
    __tablename__ = "documents"

    id = Column(String(64), primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=True)
    uploader_id = Column(String(64), nullable=True)
    upload_date = Column(DATETIME(fsp=6), default=utc_now, nullable=False)
    status = Column(String(32), default="uploaded", nullable=False)
    chunk_count = Column(Integer, default=0, nullable=False)
    version = Column(String(32), default="v1", nullable=False)
    created_at = Column(DATETIME(fsp=6), default=utc_now, nullable=False)
    updated_at = Column(DATETIME(fsp=6), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_documents_status", "status"),
        Index("ix_documents_version", "version"),
    )

    def __repr__(self):
        return f"<DocumentModel(id='{self.id}', filename='{self.filename}', status='{self.status}', version='{self.version}')>"


class ChatSessionModel(Base):
    """
    Tracks conversation sessions for users or anonymous sessions.
    SRS Section 9.1:
        id, user_id where authentication is enabled, title, created_at
    """
    __tablename__ = "chat_sessions"

    id = Column(String(64), primary_key=True, index=True)
    user_id = Column(String(64), nullable=True)
    title = Column(String(255), nullable=False, default="New Conversation")
    created_at = Column(DATETIME(fsp=6), default=utc_now, nullable=False)
    updated_at = Column(DATETIME(fsp=6), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationship to messages
    messages = relationship(
        "MessageModel",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="MessageModel.created_at, MessageModel.id",
    )

    __table_args__ = (
        Index("ix_chat_sessions_user_id", "user_id"),
        Index("ix_chat_sessions_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<ChatSessionModel(id='{self.id}', user_id='{self.user_id}', title='{self.title}')>"


class MessageModel(Base):
    """
    Stores individual messages within a chat session.
    SRS Section 9.1:
        id, session_id, role, content, timestamp, source references, cache-hit indicator
    """
    __tablename__ = "messages"

    id = Column(String(64), primary_key=True, index=True)
    session_id = Column(String(64), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(32), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    timestamp = Column(DATETIME(fsp=6), default=utc_now, nullable=False)
    source_references = Column(JSON, nullable=True)  # Structured citations JSON
    is_cache_hit = Column(Boolean, default=False, nullable=False)
    created_at = Column(DATETIME(fsp=6), default=utc_now, nullable=False)

    # Relationship to chat session
    session = relationship("ChatSessionModel", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_session_id_created_at", "session_id", "created_at"),
        Index("ix_messages_is_cache_hit", "is_cache_hit"),
    )

    def __repr__(self):
        return f"<MessageModel(id='{self.id}', session_id='{self.session_id}', role='{self.role}', is_cache_hit={self.is_cache_hit})>"
