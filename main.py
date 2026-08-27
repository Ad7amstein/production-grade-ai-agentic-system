"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.v1 import v1_router
from config.settings import settings
from system.logs import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown lifecycle."""

    logger.info(
        "application_startup",
        project_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        api_version=settings.API_VERSION,
    )
    try:
        yield
    finally:
        logger.info("application_shutdown")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_VERSION}/openapi.json",
    lifespan=lifespan,
)

app.include_router(v1_router)
