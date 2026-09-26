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
from data.repositories import UserSessionRepository
from data.schemas import User, UserSession
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


def create_token_pair(id: str, sid: str, expires_delta: Optional[timedelta] = None) -> Token:
    """Create a JWT access/refresh token pair for the given subject and session.

    Both tokens carry the same ``sid``, so revoking that session's row
    invalidates the access and refresh token together.

    Args:
        id: Subject identifier (user ID) encoded in the token claims.
        sid: ``UserSession.id`` this pair belongs to.
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
        "sid": sid,
        "exp": access_expire,
        "iat": now,
        "jti": f"{id}-{now.timestamp()}",
        "type": "access",
    }
    refresh_claims = {
        "sub": id,
        "sid": sid,
        "exp": refresh_expire,
        "iat": now,
        "jti": f"{id}-refresh-{now.timestamp()}",
        "type": "refresh",
    }

    access_token = jwt.encode(access_claims, settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM)
    refresh_token = jwt.encode(refresh_claims, settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM)

    logger.info("token_pair_created", id=id, sid=sid, access_expires_at=access_expire.isoformat())

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=access_expire,
        token_type="bearer",
    )


def verify_token(token: str, token_type: str = "access") -> Optional[dict]:
    """Decode and validate a JWT, returning its claims on success.

    Args:
        token: Encoded JWT string to verify.
        token_type: Expected ``type`` claim value (``"access"`` or ``"refresh"``).

    Returns:
        The decoded claims (``sub``, ``sid``, ``exp``, ``iat``, ``jti``, ``type``)
        if the token is valid and its type matches, ``None`` otherwise.
    """
    if not token or not isinstance(token, str):
        logger.warning("token_invalid_format")
        return None

    try:
        claims = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        id: str | None = claims.get("sub")
        if id is None or not isinstance(id, str):
            logger.warning("token_missing_id")
            return None

        if claims.get("type") != token_type:
            logger.warning("token_type_mismatch", expected=token_type, got=claims.get("type"))
            return None

        logger.debug("token_verified", id=id, token_type=token_type)
        return claims

    except ExpiredSignatureError:
        logger.info("token_expired")
        return None

    except JWTClaimsError:
        logger.warning("token_claims_invalid")
        return None

    except JWTError:
        logger.warning("token_invalid")
        return None


def session_id_from(claims: dict) -> Optional[UUID]:
    """Extract and parse the ``sid`` claim from decoded token claims.

    Args:
        claims: Claims returned by ``verify_token``.

    Returns:
        The session UUID, or ``None`` if the claim is missing or malformed.
    """
    sid = claims.get("sid")
    if not isinstance(sid, str):
        return None
    try:
        return UUID(sid)
    except ValueError:
        return None


async def get_current_session(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db_session: AsyncSession = Depends(db_manager.get_db_session),
) -> UserSession:
    """FastAPI dependency returning the live session behind the current request.

    A token is only usable while its session row is live, so rotating or
    revoking that row invalidates the access token immediately rather than
    leaving it valid until expiry.

    Args:
        credentials: Bearer token extracted by HTTPBearer.
        db_session: Async database session injected by FastAPI.

    Returns:
        The live UserSession, with its owning ``user`` eager-loaded.

    Raises:
        HTTPException: 401 if the token is invalid, or its session has been
            revoked, has expired, or never existed.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    claims = verify_token(credentials.credentials)
    if claims is None:
        raise credentials_exception

    session_id = session_id_from(claims)
    if session_id is None:
        raise credentials_exception

    session = await UserSessionRepository(db_session).get_live(session_id)
    if session is None:
        logger.info("session_not_live", session_id=str(session_id))
        raise credentials_exception

    bind_contextvars(user_id=str(session.user_id), session_id=str(session.id))
    return session


async def get_current_user(session: UserSession = Depends(get_current_session)) -> User:
    """FastAPI dependency returning the authenticated, active user for the current request.

    Delegates session validity to ``get_current_session`` so every
    authenticated route shares the same live-session check, not just the
    ones that use the session directly.

    Args:
        session: The live session behind the request, with ``user`` eager-loaded.

    Returns:
        The authenticated and active User instance.

    Raises:
        HTTPException: 403 if the account is inactive.
    """
    user = session.user
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    return user


def main():
    """Entry Point for the Program."""
    print(f"Welcome from `{os.path.basename(__file__).split('.')[0]}` Module. Nothing to do ^_____^!")


if __name__ == "__main__":
    main()
