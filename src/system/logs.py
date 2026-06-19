"""Logging configuration and setup for the application.

This module provides structured logging configuration using structlog,
with environment-specific formatters and handlers. It supports both
console-friendly development logging and JSON-formatted production logging.
"""

import os
import sys
from pathlib import Path
import logging
from typing import List, Any
from concurrent_log_handler import ConcurrentRotatingFileHandler
import structlog
from config.settings import settings, LogRenderer, Environment


def get_log_file_path() -> Path:
    """Get the current log file path based on the environment.

    Returns:
        Path: The path to the log file
    """

    env_name = str(settings.APP_ENV)

    file_path = Path(
        str(settings.LOG_DIR),
        f"{env_name}-logs.jsonl",
    )

    file_path.parent.mkdir(parents=True, exist_ok=True)
    return file_path


def get_structlog_processors(include_file_info: bool = True) -> List[Any]:
    """Get the structlog processors based on configuration.

    Args:
        include_file_info: Whether to include file information in the logs

    Returns:
        List[Any]: List of structlog processors
    """
    # Set up processors that are common to both outputs
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.contextvars.merge_contextvars,
    ]

    # Add callsite parameters if file info is requested
    if include_file_info:
        processors.append(
            structlog.processors.CallsiteParameterAdder(
                {
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                    structlog.processors.CallsiteParameter.MODULE,
                    structlog.processors.CallsiteParameter.PATHNAME,
                }
            )
        )

    # Add environment info
    processors.append(
        lambda _, __, event_dict: {**event_dict, "environment": str(settings.APP_ENV)}
    )

    return processors


def sort_event_keys(_, __, event_dict):
    """Sort event keys based on priority and alphabetically."""
    priority_keys = [
        "timestamp",
        "level",
        "event",
        "logger",
        "environment",
        "pathname",
        "filename",
        "module",
        "func_name",
        "lineno",
    ]

    ordered = {}

    # Add priority keys first
    for key in priority_keys:
        if key in event_dict:
            ordered[key] = event_dict.pop(key)

    # Add remaining keys alphabetically
    for key in sorted(event_dict):
        ordered[key] = event_dict[key]

    return ordered


def setup_logging() -> None:
    """Configure structlog with different formatters based on environment.

    In development: pretty console output
    In staging/production: structured JSON logs
    """
    log_level = str(settings.LOG_LEVEL)

    # Create console handler
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(
            colors=settings.LOG_RENDERER == LogRenderer.CONSOLE
        )
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)

    # Create file handler for JSON logs
    json_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer()
    )
    file_handler = ConcurrentRotatingFileHandler(
        get_log_file_path(),
        mode="a",
        encoding="utf-8",
        maxBytes=settings.LOG_MAX_BYTES,  # type: ignore
        backupCount=settings.LOG_BACKUP_COUNT,  # type: ignore
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(json_formatter)

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        handlers=[file_handler, console_handler],
        force=True,
    )

    shared_processors = get_structlog_processors(
        include_file_info=settings.APP_ENV
        in [Environment.STAGING, Environment.PRODUCTION]
    )

    # Configure structlog based on environment
    structlog.configure(
        processors=[
            *shared_processors,
            sort_event_keys,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Initialize logging
setup_logging()

# Create logger instance
logger = structlog.get_logger()


def main():
    """Entry Point for the Program."""
    print(
        f"Welcome from `{os.path.basename(__file__).split('.')[0]}` Module. Nothing to do ^_____^!"
    )
    print(get_log_file_path())
    logger.info(
        "logging_initialized %s",
        "Adham",
        environment=str(settings.APP_ENV),
        log_level=str(settings.LOG_LEVEL),
        log_renderer=str(settings.LOG_RENDERER),
        debug=settings.DEBUG,
    )
    logger.info(
        "logging_initialized",
        environment=str(settings.APP_ENV),
        log_level=str(settings.LOG_LEVEL),
        log_renderer=str(settings.LOG_RENDERER),
        debug=settings.DEBUG,
    )
    logger.debug(
        "test_debug",
        environment=str(settings.APP_ENV),
        log_level=str(settings.LOG_LEVEL),
        log_renderer=str(settings.LOG_RENDERER),
        debug=settings.DEBUG,
    )
    logger.warning(
        "test_warning",
        environment=str(settings.APP_ENV),
        log_level=str(settings.LOG_LEVEL),
        log_renderer=str(settings.LOG_RENDERER),
        debug=settings.DEBUG,
    )
    logger.error(
        "test_error",
        environment=str(settings.APP_ENV),
        log_level=str(settings.LOG_LEVEL),
        log_renderer=str(settings.LOG_RENDERER),
        debug=settings.DEBUG,
    )


if __name__ == "__main__":
    main()
