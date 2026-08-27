"""API v1 routers package."""

from .auth import router as auth_router
from .base import router as base_router

__all__ = ["base_router", "auth_router"]
