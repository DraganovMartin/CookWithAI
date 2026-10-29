"""LLM backend calling OpenRouter's OpenAI-compatible chat completions API."""

import logging
import re

import httpx
from pydantic import BaseModel, ValidationError

from app.llm import prompts
from app.llm.base import LLMError
from app.llm.schemas import RecipeDetails, RecipeSuggestion, SuggestionList

logger = logging.getLogger(__name__)

_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def strip_code_fences(content: str) -> str:
    """Some models wrap JSON in ```json fences even in JSON mode."""
    return _CODE_FENCE.sub("", content.strip())


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float = 60,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._model = model
        self._http = http_client or httpx.Client(
            base_url=base_url,
            timeout=timeout_seconds,
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Title": "CookWithAI",
            },
        )

    def suggest_recipes(self, available_ingredients: list[str]) -> list[RecipeSuggestion]:
        result = self._complete_json(
            prompts.SUGGEST_SYSTEM_PROMPT,
            prompts.build_suggest_prompt(available_ingredients),
            SuggestionList,
        )
        return result.suggestions

    def get_recipe_details(
        self, suggestion: RecipeSuggestion, available_ingredients: list[str]
    ) -> RecipeDetails:
        return self._complete_json(
            prompts.DETAILS_SYSTEM_PROMPT,
            prompts.build_details_prompt(suggestion, available_ingredients),
            RecipeDetails,
        )

    def _complete_json[T: BaseModel](self, system: str, user: str, schema: type[T]) -> T:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.7,
        }
        last_error: Exception | None = None
        for attempt in range(1, 3):  # one retry on malformed output
            try:
                response = self._http.post("/chat/completions", json=payload)
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return schema.model_validate_json(strip_code_fences(content))
            except ValidationError as exc:
                logger.warning("Attempt %d: LLM response did not match schema: %s", attempt, exc)
                last_error = exc
            except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
                raise LLMError(f"OpenRouter request failed: {exc}") from exc
        raise LLMError("The model returned an invalid response twice") from last_error
