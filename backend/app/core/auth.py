"""
CampusMind AI - Authentication & Role Authorization Dependencies
Provides reusable FastAPI dependencies for:
1. Extracting and validating JWT bearer tokens (get_current_user).
2. Role verification (require_role, require_admin, require_staff_or_admin).
3. Public vs protected endpoint access control per SRS Version 1.2 & 1.3.
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


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db_session),
) -> UserModel:
    """
    Validates JWT token from the Authorization header and resolves the user from MySQL.
    Raises 401 Unauthorized if missing, invalid, or expired.
    """
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


def require_roles(allowed_roles: List[str]) -> Callable:
    """
    Factory dependency checking if the authenticated user has one of the allowed roles.
    Raises 403 Forbidden if user's role is not authorized.
    """
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

