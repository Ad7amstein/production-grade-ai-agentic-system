"""Async PostgreSQL engine and session management.

Provides a single entry point for engine creation, connection pooling,
session lifecycle, and table initialisation using SQLAlchemy async ORM.
"""

import os
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.settings import Environment, settings
from system.logs import logger


class DatabaseManager:
    """Manages the async SQLAlchemy engine and session factory.

    Reads all connection and pool parameters from ``settings`` on
    construction.  The single instance is intended to be shared across
    the application lifetime.

    Attributes:
        db_engine (AsyncEngine): The underlying async database engine.
        session_factory (async_sessionmaker): Factory for creating
            ``AsyncSession`` instances.
    """

    def __init__(self):
        """Initialise engine and session factory from application settings.

        Raises:
            SQLAlchemyError: If engine creation fails and the environment
                is not ``PRODUCTION``.
        """
        # Create engine with appropriate pool configuration
        connection_url = (
            f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
            f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
        )

        try:
            self.db_engine = create_async_engine(
                connection_url,
                pool_pre_ping=True,
                pool_size=settings.POSTGRES_POOL_SIZE,
                max_overflow=settings.POSTGRES_MAX_OVERFLOW,
                pool_timeout=30,
                pool_recycle=1800,
                echo=settings.DEBUG,
            )

            self.session_factory = async_sessionmaker(
                self.db_engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
        except SQLAlchemyError as e:
            logger.error(
                "database_engine_creation_failed",
                error=str(e),
                environment=str(settings.APP_ENV),
            )
            if settings.APP_ENV != Environment.PRODUCTION:
                raise

    async def check_connection(self) -> None:
        """Verify the database is reachable."""

        try:
            async with self.db_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

        except Exception:
            logger.critical("database_connection_failed")
            raise

    async def get_db_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Yield a database session, rolling back automatically on error.

        Designed for use as a FastAPI dependency or async context manager.
        The session is closed when the generator exits.

        Yields:
            AsyncSession: A transactional database session.

        Raises:
            Exception: Re-raises any exception after rolling back the
                session.
        """
        async with self.session_factory() as db_session:
            try:
                yield db_session
                await db_session.commit()
            except Exception:
                await db_session.rollback()
                raise

    async def dispose(self) -> None:
        """Dispose the engine and close all pooled connections.

        Should be called on application shutdown to release database
        resources cleanly.
        """
        await self.db_engine.dispose()


db_manager = DatabaseManager()


def main():
    """Entry Point for the Program."""
    print(f"Welcome from `{os.path.basename(__file__).split('.')[0]}` Module. Nothing to do ^_____^!")


if __name__ == "__main__":
    main()
