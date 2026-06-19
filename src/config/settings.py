"""Application configuration management.

This module handles environment-specific configuration loading, parsing, and management
for the application. It includes environment detection, .env file loading, and
configuration value parsing.
"""

import os
from typing import Optional
from enum import StrEnum
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, model_validator


class Environment(StrEnum):
    """Application environment types.

    Defines the possible environments the application can run in:
    development, staging, production, and test.

    Attributes:
        DEVELOPMENT (str): The development environment.
        STAGING (str): The staging environment.
        PRODUCTION (str): The production environment.
        TEST (str): The test environment.
    """

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class LogLevel(StrEnum):
    """Log level types.

    Defines the possible log levels for the application.

    Attributes:
        DEBUG (str): Debug log level.
        INFO (str): Info log level.
        WARNING (str): Warning log level.
        ERROR (str): Error log level.
    """

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LogRenderer(StrEnum):
    """Log renderer types.

    Defines the possible log renderers for the application.

    Attributes:
        CONSOLE (str): Console log renderer.
        JSON (str): JSON log renderer.
    """

    CONSOLE = "console"
    JSON = "json"


def get_environment() -> Environment:
    """Get the current environment.

    Must be set via export APP_ENV=development|staging|production|test.
    it will be used to load the appropriate .env file only.

    Returns:
        Environment: The current environment (development, staging, production, or test)
    """
    match os.getenv("APP_ENV", "development").lower():
        case "production" | "prod":
            return Environment.PRODUCTION
        case "staging" | "stage":
            return Environment.STAGING
        case "testing" | "test":
            return Environment.TEST
        case _:
            return Environment.DEVELOPMENT


def load_env_file() -> str | Path | None:
    """Load environment-specific .env file.

    Returns:
        str | Path | None: The path to the loaded .env file, or None if no file was found.
    """
    env = get_environment()
    print(f"Loading environment: {env}")
    base_dir = Path(__file__).parents[2]

    # Define env files in priority order
    env_files = [Path(base_dir, f".env.{env.value}"), Path(base_dir, ".env")]

    # Load the first env file that exists
    for env_file in env_files:
        if env_file.is_file():
            load_dotenv(env_file, override=True)
            print(f"Loaded environment from {env_file}")
            return env_file

    # Fallback to default if no env file found
    return None


ENV_FILE = load_env_file()

ENV_DEFAULTS = {
    Environment.DEVELOPMENT: {
        "DEBUG": True,
        "LOG_LEVEL": LogLevel.DEBUG,
        "LOG_RENDERER": LogRenderer.CONSOLE,
    },
    Environment.STAGING: {
        "DEBUG": False,
        "LOG_LEVEL": LogLevel.INFO,
        "LOG_RENDERER": LogRenderer.JSON,
    },
    Environment.PRODUCTION: {
        "DEBUG": False,
        "LOG_LEVEL": LogLevel.WARNING,
        "LOG_RENDERER": LogRenderer.JSON,
    },
    Environment.TEST: {
        "DEBUG": True,
        "LOG_LEVEL": LogLevel.DEBUG,
        "LOG_RENDERER": LogRenderer.CONSOLE,
    },
}


def parse_list_from_env(
    env_key: str, delimiter: str = ",", default=None
) -> list | None:
    """Parse an environment variable into a list.

    Args:
        env_key: The environment variable name.
        delimiter: The delimiter used to split values.
        default: The value to return when the environment variable is unset.

    Returns:
        A list of parsed values, or the default value if unset.
    """
    value = os.getenv(env_key)
    if value is None:
        return default or None

    # Remove quotes if they exist
    value = value.strip("\"'")
    # Handle single value case
    if delimiter not in value:
        return [value]

    # Split comma-seperated values
    return [item.strip() for item in value.split(delimiter) if item.strip()]


class Settings(BaseSettings):
    """Application settings configuration.

    Manages application configuration with support for environment-specific
    settings and validation of environment aliases.
    """

    APP_ENV: Environment = Field(...)
    PROJECT_NAME: str = Field(..., max_length=100)
    VERSION: str = Field(...)
    PROJECT_ROOT: str = Field(...)

    # ==================================================
    # Logging Settings
    # ==================================================
    DEBUG: Optional[bool] = Field(default=None)
    LOG_LEVEL: Optional[LogLevel] = Field(default=None)
    LOG_RENDERER: Optional[LogRenderer] = Field(default=None)
    LOG_DIR: Optional[str] = Field(default="storage/logs")
    LOG_MAX_BYTES: Optional[int] = Field(default=10 * 1024 * 1024)  # 10 MB
    LOG_BACKUP_COUNT: Optional[int] = Field(default=10)

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8")

    @model_validator(mode="after")
    def configure_environment_defaults(self):
        """Configure environment-specific default values.

        Returns:
            Settings: The settings instance with environment defaults applied.
        """
        current_env_defaults = ENV_DEFAULTS.get(self.APP_ENV, {})

        for key, value in current_env_defaults.items():
            if getattr(self, key, None) is None:
                setattr(self, key, value)

        return self

    @field_validator("APP_ENV", mode="before")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        """Normalize APP_ENV aliases to supported environment values.

        Args:
            value: The input environment value to normalize.

        Returns:
            str: The normalized environment value.
        """
        if isinstance(value, Environment):
            return value

        aliases = {
            "dev": "development",
            "development": "development",
            "stage": "staging",
            "staging": "staging",
            "prod": "production",
            "production": "production",
            "test": "test",
            "testing": "test",
        }

        normalized_env = aliases.get(str(value).lower())
        if normalized_env is None:
            raise ValueError(
                f"Invalid APP_ENV '{value}'."
                f"Expected one of: {', '.join(sorted(aliases.keys()))}"
            )

        return normalized_env


# Create settings instance
settings = Settings()  # type: ignore


def main():
    """Entry Point for the Program."""
    print(
        f"Welcome from `{os.path.basename(__file__).split('.')[0]}` Module. Nothing to do ^_____^!"
    )
    for key, value in settings.model_dump().items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
