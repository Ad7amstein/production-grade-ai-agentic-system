"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.v1 import v1_router
from config.settings import settings
from data.db_manager import db_manager
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

    await db_manager.check_connection()
    logger.info("database_connection_successful")

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


@app.exception_handler(ConnectionRefusedError)
async def connection_refused_handler(request: Request, _exc: ConnectionRefusedError):
    """Log the error and return 503 when the database connection is refused."""
    logger.exception(
        "database_error",
        path=request.url.path,
        method=request.method,
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "Service temporarily unavailable."},
    )
