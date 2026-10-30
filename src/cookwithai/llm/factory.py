"""Picks the LLM backend from settings."""

from cookwithai.config import Settings
from cookwithai.llm.base import LLMClient
from cookwithai.llm.mock_client import MockLLMClient
from cookwithai.llm.openrouter_client import OpenRouterClient


def get_llm_client(settings: Settings) -> LLMClient:
    match settings.llm_provider:
        case "mock":
            return MockLLMClient()
        case "openrouter":
            if not settings.openrouter_api_key:
                raise ValueError("LLM_PROVIDER=openrouter requires OPENROUTER_API_KEY to be set")
            return OpenRouterClient(
                api_key=settings.openrouter_api_key,
                model=settings.openrouter_model,
                base_url=settings.openrouter_base_url,
            )
        case other:
            raise ValueError(f"Unknown LLM_PROVIDER {other!r}; expected 'mock' or 'openrouter'")
