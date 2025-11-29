"""Utility helpers for creating chat models with fallbacks."""

import importlib
from typing import Optional

from config.agent_config import AGENT_CONFIG
from config.settings import settings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from utils.logger import setup_logger

# Attempt to import Anthropic chat model dynamically to avoid hard dependency
ChatAnthropic = None
try:  # pragma: no cover - optional dependency
    anthropic_module = importlib.import_module("langchain_anthropic")
    ChatAnthropic = getattr(anthropic_module, "ChatAnthropic", None)
except ImportError:
    print("langchain_anthropic package not installed; Anthropic models will be unavailable.")
    ChatAnthropic = None

logger = setup_logger(__name__)


def get_llm(agent_name: str) -> BaseChatModel:
    """Create a chat model for an agent with optional fallback.

    The function tries to create an OpenAI chat model first.
    If OpenAI credentials are missing or the model fails to run,
    and an Anthropic API key plus fallback model are available,
    it creates a Claude model as a fallback and wraps it using
    LangChain's `with_fallbacks` helper.
    """
    config = AGENT_CONFIG.get(agent_name)
    if not config:
        raise ValueError(f"No agent configuration found for '{agent_name}'")

    temperature = config.get("temperature", 0.3)
    primary_model_name = config.get("model")
    fallback_model_name = config.get("fallback_model")

    primary_llm: Optional[BaseChatModel] = None
    fallback_llm: Optional[BaseChatModel] = None

    # Try OpenAI first
    if settings.openai_api_key and primary_model_name:
        try:
            primary_llm = ChatOpenAI(
                model=primary_model_name,
                temperature=temperature,
                api_key=settings.openai_api_key,
            )
        except Exception as e:
            logger.warning(
                "Failed to initialize OpenAI model '%s' for %s: %s",
                primary_model_name,
                agent_name,
                e,
            )

    # Prepare Anthropic fallback if available
    if settings.anthropic_api_key and fallback_model_name and ChatAnthropic:
        try:
            fallback_llm = ChatAnthropic(
                model=fallback_model_name,
                temperature=temperature,
                anthropic_api_key=settings.anthropic_api_key,
            )
        except Exception as e:
            logger.warning(
                "Failed to initialize Anthropic fallback model '%s' for %s: %s",
                fallback_model_name,
                agent_name,
                e,
            )
    elif fallback_model_name and not ChatAnthropic:
        logger.warning(
            "langchain_anthropic package not installed; cannot use fallback model '%s' for %s",
            fallback_model_name,
            agent_name,
        )

    if primary_llm and fallback_llm:
        logger.info(
            "Configured OpenAI model '%s' with Claude fallback '%s' for %s",
            primary_model_name,
            fallback_model_name,
            agent_name,
        )
        return primary_llm.with_fallbacks([fallback_llm])

    if primary_llm:
        logger.info(
            "Configured OpenAI model '%s' for %s (no fallback available)",
            primary_model_name,
            agent_name,
        )
        return primary_llm

    if fallback_llm:
        logger.info(
            "Using Claude fallback model '%s' as primary for %s",
            fallback_model_name,
            agent_name,
        )
        return fallback_llm

    raise RuntimeError(
        f"Unable to configure chat model for '{agent_name}'. "
        "Ensure OpenAI or Anthropic credentials are provided."
    )

