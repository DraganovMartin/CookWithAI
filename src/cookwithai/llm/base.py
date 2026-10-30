"""The interface every LLM backend implements."""

from typing import Protocol

from cookwithai.llm.schemas import RecipeDetails, RecipeSuggestion


class LLMError(Exception):
    """Raised when the LLM backend fails or returns an unusable response."""


class LLMClient(Protocol):
    def suggest_recipes(self, available_ingredients: list[str]) -> list[RecipeSuggestion]:
        """Return ~3 suggestions: 1-2 using only the given ingredients, 1-2 needing a few extra."""
        ...

    def get_recipe_details(
        self, suggestion: RecipeSuggestion, available_ingredients: list[str]
    ) -> RecipeDetails:
        """Expand one suggestion into a full recipe with quantities and steps."""
        ...
