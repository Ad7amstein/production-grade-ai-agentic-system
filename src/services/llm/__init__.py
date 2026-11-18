"""LLM service: builds chat models for the agent."""

from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from pydantic import SecretStr

from config.settings import settings
from services.llm.model_profiles import MODEL_PROFILES
from system.logs import logger


def build_chat_model(  # pylint: disable=[R0913]
    *,
    model: str,
    model_provider: str,
    profile: dict[str, Any],
    max_tokens: int,
    base_url: str = settings.LLM_BASE_URL,
    api_key: SecretStr = settings.SOVEREIGNEG_API_KEY,
    max_retries: int = settings.DEFAULT_GENERATION_MAX_RETRIES,
    temperature: float = settings.DEFAULT_GENERATION_TEMPERATURE,
    timeout: float = settings.LLM_REQUEST_TIMEOUT_SECONDS,
) -> BaseChatModel:
    """Build a chat model; connection and sampling arguments default to the generation settings.

    Args:
        model (str): Model name, e.g. `settings.GENERATION_MODEL`.
        model_provider (str): LangChain provider used to build the client, e.g. `"openai"`.
        profile (dict[str, Any]): Model profile, e.g. an entry of `MODEL_PROFILES`.
        max_tokens (int): Maximum number of tokens the model may generate per call.
        base_url (str): API base URL.
        api_key (SecretStr): API key for `base_url`.
        max_retries (int): Retries on transient API errors.
        temperature (float): Sampling temperature.
        timeout (float): Seconds before one API call fails, so a stalled upstream cannot hang a request forever.

    Returns:
        BaseChatModel: A LangChain chat model ready for invocation.
    """
    chat_model = init_chat_model(
        model=model,
        model_provider=model_provider,
        profile=profile,
        base_url=base_url,
        api_key=api_key,
        max_tokens=max_tokens,
        temperature=temperature,
        max_retries=max_retries,
        timeout=timeout,
    )
    logger.info("llm_created", model=model, max_tokens=max_tokens)
    return chat_model


__all__ = ["build_chat_model", "MODEL_PROFILES"]
