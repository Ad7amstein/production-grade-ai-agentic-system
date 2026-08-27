"""V1 API router aggregating all versioned sub-routers."""

from fastapi import APIRouter

from .routers import base_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(base_router, tags=["health"])
