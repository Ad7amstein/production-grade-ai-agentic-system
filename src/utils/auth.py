# pylint: disable=[W0622, W0707]

"""JWT token creation and verification utilities."""

import os
from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import UUID

import bcrypt as _bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.contextvars import bind_contextvars

from config.settings import settings
from data.db_manager import db_manager
from data.models.auth import Token
from data.repositories import UserRepository
from data.schemas import User
from system.logs import logger

security = HTTPBearer()


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt.

    Args:
        password: Plaintext password to hash.

    Returns:
        Bcrypt-hashed password string.
    """
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash.

    Args:
        plain: Plaintext password to check.
        hashed: Bcrypt hash to check against.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token_pair(id: str, expires_delta: Optional[timedelta] = None) -> Token:
    """Create a JWT access/refresh token pair for the given subject.

    Args:
        id: Subject identifier (user ID) encoded in the token claims.
        expires_delta: Custom access token lifetime. Defaults to
            ``JWT_ACCESS_TOKEN_EXPIRE_MINUTES`` from settings.

    Returns:
        Token containing signed access and refresh JWTs with expiry metadata.
    """
    now = datetime.now(UTC)

    access_expire = now + (expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_expire = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    access_claims = {
        "sub": id,
        "exp": access_expire,
        "iat": now,
        "jti": f"{id}-{now.timestamp()}",
        "type": "access",
    }
    refresh_claims = {
        "sub": id,
        "exp": refresh_expire,
        "iat": now,
        "jti": f"{id}-refresh-{now.timestamp()}",
        "type": "refresh",
    }

    access_token = jwt.encode(access_claims, settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM)
    refresh_token = jwt.encode(refresh_claims, settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM)

    logger.info("token_pair_created", id=id, access_expires_at=access_expire.isoformat())

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=access_expire,
        token_type="bearer",
    )


def verify_token(token: str, token_type: str = "access") -> Optional[str]:
    """Decode and validate a JWT, returning the subject claim on success.

    Args:
        token: Encoded JWT string to verify.
        token_type: Expected ``type`` claim value (``"access"`` or ``"refresh"``).

    Returns:
        The ``sub`` claim (user ID) if the token is valid and type matches, ``None`` otherwise.
    """
    try:
        if not token or not isinstance(token, str):
            logger.warning("token_invalid_format")
            return None

        claims = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        id: str | None = claims.get("sub")
        if id is None:
            logger.warning("token_missing_id")
            return None

        if not isinstance(id, str):
            logger.warning("token_invalid_subject")
            return None

        if claims.get("type") != token_type:
            logger.warning("token_type_mismatch", expected=token_type, got=claims.get("type"))
            return None

        logger.debug("token_verified", id=id, token_type=token_type)
        return id

    except ExpiredSignatureError:
        logger.info("token_expired")
        return None

    except JWTClaimsError:
        logger.warning("token_claims_invalid")
        return None

    except JWTError:
        logger.warning("token_invalid")
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db_session: AsyncSession = Depends(db_manager.get_db_session),
) -> User:
    """FastAPI dependency returning the authenticated, active user for the current request.

    Args:
        credentials: Bearer token extracted by HTTPBearer.
        db_session: Async database session injected by FastAPI.

    Returns:
        The authenticated and active User instance.

    Raises:
        HTTPException: 401 if the token is invalid or the user does not exist.
        HTTPException: 403 if the account is inactive.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = verify_token(credentials.credentials)
    if user_id is None:
        raise credentials_exception

    try:
        uid = UUID(user_id)
    except ValueError:
        raise credentials_exception

    user = await UserRepository(db_session).get(uid)
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled",
        )

    bind_contextvars(user_id=str(user.id))
    return user


def main():
    """Entry Point for the Program."""
    print(f"Welcome from `{os.path.basename(__file__).split('.')[0]}` Module. Nothing to do ^_____^!")


if __name__ == "__main__":
    main()
