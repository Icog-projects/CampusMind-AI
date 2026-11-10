"""CampusMind AI - Authentication & Role Authorization Dependencies.

Provides JWT validation and role-based access control dependencies.

Responsibilities:
1. get_current_user(): Validates the incoming JWT bearer token and resolves the active user record.
2. require_roles(): Factory creating authorization dependencies for permitted user roles.
"""

import logging
from typing import List, Optional, Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.core.security import decode_access_token
from app.models.db_models import UserModel
from app.repositories.database_repository import UserRepository

logger = logging.getLogger(__name__)

security_bearer = HTTPBearer(auto_error=False)


# Validates JWT token from the Authorization header and resolves the user from MySQL.
def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db_session),
) -> UserModel:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as e:
        logger.warning("JWT validation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User belonging to this token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# Factory dependency checking if the authenticated user has one of the allowed roles.
def require_roles(allowed_roles: List[str]) -> Callable:
    def role_checker(current_user: UserModel = Depends(get_current_user)) -> UserModel:
        clean_user_role = current_user.role.strip().lower()
        clean_allowed = [r.strip().lower() for r in allowed_roles]

        if clean_user_role not in clean_allowed:
            logger.warning(
                "Access denied for user %s (role: %s); required: %s",
                current_user.email,
                current_user.role,
                allowed_roles,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of the following roles: {', '.join(allowed_roles)}.",
            )
        return current_user

    return role_checker


# Convenient role dependencies
require_admin = require_roles(["admin"])
require_staff_or_admin = require_roles(["staff", "admin"])
require_authenticated_user = get_current_user

