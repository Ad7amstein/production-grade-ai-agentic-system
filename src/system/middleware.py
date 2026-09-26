"""ASGI middleware for request-scoped logging context.

Ensures structlog contextvars do not leak between requests.
"""

import os
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from structlog.contextvars import clear_contextvars

from system.logs import logger


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware that clears structlog contextvars around each request."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Clear contextvars before and after handling a request.

        Args:
            request: Incoming ASGI request.
            call_next: Callable that forwards the request to the next
                middleware/handler and returns its response.

        Returns:
            Response: The response produced downstream.
        """
        logger.info("clearning_context_1")
        clear_contextvars()
        try:
            logger.info("calling_next")
            return await call_next(request)
        finally:
            logger.info("clearning_context_2")
            clear_contextvars()


def main():
    """Entry Point for the Program."""
    print(f"Welcome from `{os.path.basename(__file__).split('.')[0]}` Module. Nothing to do ^_____^!")


if __name__ == "__main__":
    main()
