"""Chat session router — CRUD endpoints protected by JWT auth."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from langchain.agents.middleware import PIIDetectionError
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from data.db_manager import db_manager
from data.models.chat_session import (
    ChatMessageCreate,
    ChatMessageRead,
    ChatSessionCreate,
    ChatSessionRead,
    ChatSessionUpdate,
)
from data.models.user import UserRead
from data.repositories import ChatSessionRepository
from data.schemas.user import User
from services.agent import agent
from system.logs import logger
from system.rate_limit import limiter
from utils.auth import get_current_user

router = APIRouter()


@router.post("", response_model=ChatSessionRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_CREATE_CHAT_SESSION)
async def create_chat_session(
    request: Request,
    response: Response,
    payload: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(db_manager.get_db_session),
) -> ChatSessionRead:
    """Create a new chat session for the authenticated user.

    Args:
        payload: Request body containing the session title.
        current_user: Authenticated user from JWT dependency.
        db_session: Injected async database session.

    Returns:
        ChatSessionRead: The newly created chat session.
    """
    chat_session = await ChatSessionRepository(db_session).create(title=payload.title, user_id=current_user.id)
    logger.info("chat_session_created", chat_session_id=str(chat_session.id))
    return ChatSessionRead.model_validate(chat_session)


@router.get("", response_model=list[ChatSessionRead])
@limiter.limit(settings.RATE_LIMIT_GET_CHAT_SESSIONS)
async def get_chat_sessions(
    request: Request,
    response: Response,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(db_manager.get_db_session),
) -> list[ChatSessionRead]:
    """List all chat sessions belonging to the authenticated user.

    Args:
        page: 1-based page number (default 1).
        page_size: Number of sessions per page (default 20).
        current_user: Authenticated user from JWT dependency.
        db_session: Injected async database session.

    Returns:
        list[ChatSessionRead]: Paginated list of chat sessions owned by the current user.
    """
    chat_sessions = await ChatSessionRepository(db_session).get_all_by_user_id(
        current_user.id, page=page, page_size=page_size
    )
    logger.info("chat_sessions_retrieved", count=len(chat_sessions))
    return [ChatSessionRead.model_validate(cs) for cs in chat_sessions]


@router.get("/{session_id}", response_model=ChatSessionRead)
@limiter.limit(settings.RATE_LIMIT_GET_CHAT_SESSION)
async def get_chat_session(
    request: Request,
    response: Response,
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(db_manager.get_db_session),
) -> ChatSessionRead:
    """Retrieve a single chat session by ID.

    Args:
        session_id: UUID of the chat session to retrieve.
        current_user: Authenticated user from JWT dependency.
        db_session: Injected async database session.

    Returns:
        ChatSessionRead: The requested chat session.

    Raises:
        HTTPException: 404 if the session does not exist.
        HTTPException: 403 if the session belongs to another user.
    """
    chat_session = await ChatSessionRepository(db_session).get(session_id)
    if chat_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
    if chat_session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return ChatSessionRead.model_validate(chat_session)


@router.patch("/{session_id}", response_model=ChatSessionRead)
@limiter.limit(settings.RATE_LIMIT_UPDATE_CHAT_SESSION)
async def update_chat_session(
    request: Request,
    response: Response,
    session_id: UUID,
    payload: ChatSessionUpdate,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(db_manager.get_db_session),
) -> ChatSessionRead:
    """Partially update a chat session's title.

    Args:
        session_id: UUID of the chat session to update.
        payload: Request body with the optional new title.
        current_user: Authenticated user from JWT dependency.
        db_session: Injected async database session.

    Returns:
        ChatSessionRead: The updated chat session.

    Raises:
        HTTPException: 404 if the session does not exist.
        HTTPException: 403 if the session belongs to another user.
    """
    repo = ChatSessionRepository(db_session)
    chat_session = await repo.get(session_id)
    if chat_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
    if chat_session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    chat_session = await repo.update(session_id, **payload.model_dump(exclude_unset=True))
    logger.info("chat_session_updated", session_id=str(session_id), user_id=str(current_user.id))
    return ChatSessionRead.model_validate(chat_session)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(settings.RATE_LIMIT_DELETE_CHAT_SESSION)
async def delete_chat_session(
    request: Request,
    response: Response,
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(db_manager.get_db_session),
) -> None:
    """Delete a chat session permanently.

    Args:
        session_id: UUID of the chat session to delete.
        current_user: Authenticated user from JWT dependency.
        db_session: Injected async database session.

    Raises:
        HTTPException: 404 if the session does not exist.
        HTTPException: 403 if the session belongs to another user.
    """
    repo = ChatSessionRepository(db_session)
    chat_session = await repo.get(session_id)
    if chat_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
    if chat_session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    await repo.delete(session_id)
    logger.info("chat_session_deleted", session_id=str(session_id), user_id=str(current_user.id))


@router.post("/{session_id}/messages", response_model=ChatMessageRead)
@limiter.limit(settings.RATE_LIMIT_CHAT)
async def send_message(
    request: Request,
    response: Response,
    session_id: UUID,
    payload: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(db_manager.get_db_session, scope="function"),
) -> ChatMessageRead:
    """Send a message to the agent within a chat session and return its reply.

    Args:
        request (Request): Incoming request, required by the rate limiter.
        response (Response): Outgoing response, used by the rate limiter for headers.
        session_id (UUID): Chat session the message belongs to.
        payload (ChatMessageCreate): Request body with the user message.
        current_user (User): Authenticated user from the JWT dependency.
        db_session (AsyncSession): Injected async database session.

    Returns:
        ChatMessageRead: The agent's reply.

    Raises:
        HTTPException: 404 if the session does not exist.
        HTTPException: 403 if the session belongs to another user.
        HTTPException: 409 if another message for this session is still being answered.
        HTTPException: 422 if the message contains blocked PII, such as a credit card number.
    """
    repo = ChatSessionRepository(db_session)
    chat_session = await repo.get(session_id)
    if chat_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
    if chat_session.user_id != current_user.id:
        logger.warning("chat_session_access_denied", chat_session_id=str(session_id), user_id=str(current_user.id))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if not await repo.try_lock(session_id):
        logger.warning("chat_session_busy", chat_session_id=str(session_id), user_id=str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A message is already being processed for this session"
        )
    try:
        reply = await agent.get_response(
            payload.content, chat_session_id=str(session_id), user=UserRead.model_validate(current_user)
        )
    except PIIDetectionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Message not sent: it contains sensitive data ({error.pii_type}). Remove it and try again.",
        ) from error
    chat_session.updated_at = func.now()  # pylint: disable=[E1102]
    logger.info("chat_message_answered", chat_session_id=str(session_id), user_id=str(current_user.id))
    return ChatMessageRead(content=reply)
