"""Application settings, read from environment variables."""

import os
from dataclasses import dataclass

DEFAULT_DATABASE_PATH = "./data/cookwithai.db"
DEFAULT_OPENROUTER_MODEL = "anthropic/claude-sonnet-5.5"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class Settings:
    database_path: str
    llm_provider: str
    openrouter_api_key: str | None
    openrouter_model: str
    openrouter_base_url: str


def get_settings() -> Settings:
    return Settings(
        database_path=os.getenv("DATABASE_PATH", DEFAULT_DATABASE_PATH),
        llm_provider=os.getenv("LLM_PROVIDER", "mock").strip().lower(),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY") or None,
        openrouter_model=os.getenv("OPENROUTER_MODEL") or DEFAULT_OPENROUTER_MODEL,
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL") or DEFAULT_OPENROUTER_BASE_URL,
    )
