"""CampusMind AI - Relational Repositories.

Encapsulates database access operations for users, refresh tokens, documents, and chat records.

Responsibilities:
Class UserRepository:
1. UserRepository.__init__(): Initializes database session for user operations.
2. UserRepository.create_user(): Persists a new user record into the database.
3. UserRepository.get_by_id(): Retrieves user account by unique user ID.
4. UserRepository.get_by_email(): Finds user record matching given email address.
5. UserRepository.list_users(): Lists user records with pagination and optional role filters.
Class RefreshTokenRepository:
6. RefreshTokenRepository.__init__(): Initializes database session for refresh token operations.
7. RefreshTokenRepository.create_token(): Persists a new hashed refresh token for a user.
8. RefreshTokenRepository.get_valid_token(): Finds an active, non-expired, non-revoked refresh token by hash.
9. RefreshTokenRepository.revoke_token(): Marks a specific refresh token as revoked.
10. RefreshTokenRepository.revoke_all_for_user(): Revokes all active refresh tokens belonging to a user.
Class DocumentRepository:
11. DocumentRepository.__init__(): Initializes database session for document operations.
12. DocumentRepository.create_document(): Inserts a new document record with status and metadata.
13. DocumentRepository.get_by_id(): Fetches document record by document ID.
14. DocumentRepository.list_documents(): Lists document records with status filters and pagination.
15. DocumentRepository.update_status(): Updates processing status, chunk count, and version of a document.
16. DocumentRepository.delete_document(): Removes document record by document ID.
Class ChatRepository:
17. ChatRepository.__init__(): Initializes database session for chat operations.
18. ChatRepository.create_session(): Creates a new conversation session record.
19. ChatRepository.get_session(): Retrieves conversation session record by session ID.
20. ChatRepository.list_sessions_for_user(): Retrieves all chat sessions owned by a specific user.
21. ChatRepository.create_message(): Records a user or assistant chat message with citations and cache flags.
22. ChatRepository.get_session_messages(): Retrieves all conversation messages for a chat session.
23. ChatRepository.delete_session(): Deletes a conversation session and cascades to its messages.
"""

import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.db_models import UserModel, DocumentModel, ChatSessionModel, MessageModel, RefreshTokenModel, utc_now


# Repository handling CRUD operations for UserModel.
class UserRepository:

    def __init__(self, session: Session):
        self.session = session

    # Creates and stores a new user account.
    def create_user(
        self,
        name: str,
        email: str,
        password_hash: str,
        role: str = "student",
        user_id: Optional[str] = None,
    ) -> UserModel:
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

    # Fetches a user by primary key.
    def get_by_id(self, user_id: str) -> Optional[UserModel]:
        return self.session.query(UserModel).filter(UserModel.id == user_id).first()

    # Fetches a user by unique lowercase email.
    def get_by_email(self, email: str) -> Optional[UserModel]:
        if not email:
            return None
        return self.session.query(UserModel).filter(UserModel.email == email.strip().lower()).first()

    # Lists users with optional role filtering.
    def list_users(self, role: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[UserModel]:
        query = self.session.query(UserModel)
        if role:
            query = query.filter(UserModel.role == role.strip().lower())
        return query.order_by(desc(UserModel.created_at)).offset(offset).limit(limit).all()


# Repository handling CRUD operations for RefreshTokenModel.
class RefreshTokenRepository:

    def __init__(self, session: Session):
        self.session = session

    # Persists a new refresh token record.
    def create_token(
        self,
        user_id: str,
        token_hash: str,
        expires_at: Any,
        token_id: Optional[str] = None,
    ) -> RefreshTokenModel:
        token_obj = RefreshTokenModel(
            id=token_id or str(uuid.uuid4()),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked=False,
        )
        self.session.add(token_obj)
        self.session.commit()
        self.session.refresh(token_obj)
        return token_obj

    # Retrieves an active, non-expired, non-revoked refresh token by hash.
    def get_valid_token(self, token_hash: str) -> Optional[RefreshTokenModel]:
        now = utc_now()
        return (
            self.session.query(RefreshTokenModel)
            .filter(
                RefreshTokenModel.token_hash == token_hash,
                RefreshTokenModel.revoked == False,
                RefreshTokenModel.expires_at > now,
            )
            .first()
        )

    # Marks a specific refresh token as revoked.
    def revoke_token(self, token_hash: str) -> bool:
        token = (
            self.session.query(RefreshTokenModel)
            .filter(RefreshTokenModel.token_hash == token_hash)
            .first()
        )
        if token and not token.revoked:
            token.revoked = True
            self.session.commit()
            return True
        return False

    # Revokes all active refresh tokens belonging to a user.
    def revoke_all_for_user(self, user_id: str) -> int:
        count = (
            self.session.query(RefreshTokenModel)
            .filter(
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.revoked == False,
            )
            .update({"revoked": True})
        )
        self.session.commit()
        return count


# Repository handling CRUD operations for DocumentModel.
class DocumentRepository:

    def __init__(self, session: Session):
        self.session = session

    # Creates and stores a new document record.
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

    # Fetches a document by primary key.
    def get_by_id(self, document_id: str) -> Optional[DocumentModel]:
        return self.session.query(DocumentModel).filter(DocumentModel.id == document_id).first()

    # Lists documents with optional status and version filtering.
    def list_documents(
        self,
        status: Optional[str] = None,
        version: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[DocumentModel]:
        query = self.session.query(DocumentModel)
        if status:
            query = query.filter(DocumentModel.status == status)
        if version:
            query = query.filter(DocumentModel.version == version)
        return query.order_by(desc(DocumentModel.upload_date)).offset(offset).limit(limit).all()

    # Updates document status, chunk count, and version.
    def update_status(
        self,
        document_id: str,
        status: str,
        chunk_count: Optional[int] = None,
        version: Optional[str] = None,
    ) -> Optional[DocumentModel]:
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

    # Deletes a document record by ID.
    def delete_document(self, document_id: str) -> bool:
        doc = self.get_by_id(document_id)
        if not doc:
            return False
        self.session.delete(doc)
        self.session.commit()
        return True


# Repository handling CRUD operations for ChatSessionModel and MessageModel.
class ChatRepository:

    def __init__(self, session: Session):
        self.session = session

    # Creates and stores a new conversation session.
    def create_session(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        title: str = "New Conversation",
    ) -> ChatSessionModel:
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

    # Fetches a session by primary key.
    def get_session(self, session_id: str) -> Optional[ChatSessionModel]:
        return self.session.query(ChatSessionModel).filter(ChatSessionModel.id == session_id).first()

    # Lists chat sessions belonging to a specific user or anonymous user.
    def list_sessions_for_user(
        self,
        user_id: Optional[str],
        limit: int = 50,
        offset: int = 0,
    ) -> List[ChatSessionModel]:
        query = self.session.query(ChatSessionModel)
        if user_id:
            query = query.filter(ChatSessionModel.user_id == user_id)
        return query.order_by(desc(ChatSessionModel.created_at)).offset(offset).limit(limit).all()

    # Stores a message within a session, including role, content, structured source citations, and cache-hit status (SRS Section 8.
    def create_message(
        self,
        session_id: str,
        role: str,
        content: str,
        source_references: Optional[List[Dict[str, Any]]] = None,
        is_cache_hit: bool = False,
        message_id: Optional[str] = None,
    ) -> MessageModel:
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

    # Retrieves messages for a session in chronological order.
    def get_session_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[MessageModel]:
        return (
            self.session.query(MessageModel)
            .filter(MessageModel.session_id == session_id)
            .order_by(MessageModel.created_at.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    # Deletes a chat session and cascades deletion of its messages.
    def delete_session(self, session_id: str) -> bool:
        session_obj = self.get_session(session_id)
        if not session_obj:
            return False
        self.session.delete(session_obj)
        self.session.commit()
        return True

