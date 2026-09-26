"""V1 API router aggregating all versioned sub-routers."""

from fastapi import APIRouter

from .routers import auth_router, base_router, chat_session_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(base_router, tags=["health"])
v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
v1_router.include_router(chat_session_router, prefix="/chat-sessions", tags=["chat-sessions"])
