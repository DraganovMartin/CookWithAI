"""Pydantic models for the structured LLM responses."""

from typing import Literal

from pydantic import BaseModel, Field, computed_field

Difficulty = Literal["easy", "medium", "hard"]


class RecipeSuggestion(BaseModel):
    title: str = Field(min_length=1)
    short_description: str
    missing_ingredients: list[str] = Field(default_factory=list)
    estimated_time_minutes: int = Field(gt=0)
    difficulty: Difficulty = "medium"

    @computed_field  # type: ignore[prop-decorator]  # pydantic's documented pattern
    @property
    def uses_only_available(self) -> bool:
        # Derived rather than trusted from the LLM, so it can never contradict missing_ingredients.
        return not self.missing_ingredients


class SuggestionList(BaseModel):
    suggestions: list[RecipeSuggestion] = Field(min_length=1, max_length=5)


class RecipeIngredient(BaseModel):
    name: str
    quantity: str
    is_missing: bool = False


class Step(BaseModel):
    number: int = Field(ge=1)
    instruction: str
    duration_minutes: int | None = None


class RecipeDetails(BaseModel):
    title: str
    servings: int = Field(ge=1)
    ingredients: list[RecipeIngredient] = Field(min_length=1)
    steps: list[Step] = Field(min_length=1)
    tips: list[str] = Field(default_factory=list)
