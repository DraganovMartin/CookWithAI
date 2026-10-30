"""Use cases for the UI: ask the LLM, persist the results, read history back."""

import logging
from collections.abc import Iterable
from dataclasses import dataclass

from app.db import repository
from app.db.database import connect
from app.llm.base import LLMClient
from app.llm.schemas import RecipeDetails, RecipeSuggestion

logger = logging.getLogger(__name__)


@dataclass
class RecipeSession:
    """One search as the UI sees it, whether fresh from the LLM or loaded from history.

    `recipe_id` is None for guests, whose searches are never stored.
    """

    recipe_id: int | None
    available_ingredients: list[str]
    suggestions: list[RecipeSuggestion]
    details: RecipeDetails | None = None
    created_at: str | None = None


def normalize_ingredients(ingredients: Iterable[str]) -> list[str]:
    """Trim, lowercase and de-duplicate while keeping the user's order."""
    seen: dict[str, None] = {}
    for item in ingredients:
        name = " ".join(item.split()).lower()
        if name:
            seen.setdefault(name, None)
    return list(seen)


def has_expected_mix(suggestions: list[RecipeSuggestion]) -> bool:
    """1-2 suggestions using only available ingredients and 1-2 needing extras."""
    complete = sum(s.uses_only_available for s in suggestions)
    extended = len(suggestions) - complete
    return 1 <= complete <= 2 and 1 <= extended <= 2


class RecipeService:
    """Recipe use cases for one user; `user_id=None` is a guest, who never touches the database."""

    def __init__(self, llm: LLMClient, db_path: str, user_id: int | None) -> None:
        self._llm = llm
        self._db_path = db_path
        self._user_id = user_id

    def suggest(self, ingredients: Iterable[str]) -> RecipeSession:
        available = normalize_ingredients(ingredients)
        if not available:
            raise ValueError("Add at least one ingredient to get suggestions.")

        suggestions = self._llm.suggest_recipes(available)
        if not has_expected_mix(suggestions):
            logger.warning("Unexpected suggestion mix for %s: %s", available, suggestions)

        if self._user_id is None:
            return RecipeSession(None, available, suggestions)

        with connect(self._db_path) as conn:
            recipe_id = repository.create_recipe_request(
                conn,
                self._user_id,
                available,
                [s.model_dump() for s in suggestions],
            )
        return RecipeSession(recipe_id, available, suggestions)

    def choose(self, session: RecipeSession, suggestion: RecipeSuggestion) -> RecipeDetails:
        details = self._llm.get_recipe_details(suggestion, session.available_ingredients)
        if session.recipe_id is not None:
            with connect(self._db_path) as conn:
                repository.save_chosen_recipe(
                    conn,
                    session.recipe_id,
                    suggestion.title,
                    details.model_dump(),
                    suggestion.missing_ingredients,
                )
        session.details = details
        return details

    def history(self, limit: int = 10) -> list[RecipeSession]:
        if self._user_id is None:
            return []
        with connect(self._db_path) as conn:
            records = repository.list_recent(conn, self._user_id, limit)
        return [self._to_session(r) for r in records]

    def load(self, recipe_id: int) -> RecipeSession | None:
        if self._user_id is None:
            return None
        with connect(self._db_path) as conn:
            record = repository.get_recipe(conn, recipe_id)
        if record is None or record.user_id != self._user_id:
            return None
        return self._to_session(record)

    @staticmethod
    def _to_session(record: repository.RecipeRecord) -> RecipeSession:
        return RecipeSession(
            recipe_id=record.id,
            available_ingredients=record.available_ingredients,
            suggestions=[RecipeSuggestion.model_validate(s) for s in record.suggested_recipes],
            details=RecipeDetails.model_validate(record.steps) if record.steps else None,
            created_at=record.created_at,
        )
