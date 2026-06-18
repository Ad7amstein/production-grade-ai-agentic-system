import os
from enum import StrEnum
from pathlib import Path
from dotenv import load_dotenv


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
