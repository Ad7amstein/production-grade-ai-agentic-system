"""Base router with core utility endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response

from config.settings import settings
from system.logs import logger
from system.rate_limit import limiter

router = APIRouter()


@router.get("/health")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def health_check(request: Request, response: Response):
    """Return application health status.

    Returns:
        dict: App name, version, current UTC datetime, and status string.
    """
    logger.info("health_check_called")
    return {
        "app_name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "current_datetime": datetime.now(UTC),
        "status": "healthy",
    }
