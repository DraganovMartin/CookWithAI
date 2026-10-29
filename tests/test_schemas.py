import pytest
from pydantic import ValidationError

from app.llm.openrouter_client import strip_code_fences
from app.llm.schemas import RecipeDetails, RecipeSuggestion, SuggestionList

VALID_SUGGESTIONS = """{"suggestions": [
  {"title": "Omelette", "short_description": "Fluffy.", "missing_ingredients": [],
   "estimated_time_minutes": 10, "difficulty": "easy"},
  {"title": "Shakshuka", "short_description": "Spicy.", "missing_ingredients": ["cumin"],
   "estimated_time_minutes": 30, "difficulty": "medium"}
]}"""


def test_parses_valid_suggestions():
    result = SuggestionList.model_validate_json(VALID_SUGGESTIONS)
    assert [s.uses_only_available for s in result.suggestions] == [True, False]


def test_uses_only_available_is_derived_not_trusted():
    suggestion = RecipeSuggestion.model_validate(
        {"title": "X", "short_description": "", "missing_ingredients": ["salt"],
         "estimated_time_minutes": 5, "uses_only_available": True}
    )
    assert suggestion.uses_only_available is False


def test_round_trips_through_model_dump():
    original = SuggestionList.model_validate_json(VALID_SUGGESTIONS).suggestions[1]
    assert RecipeSuggestion.model_validate(original.model_dump()) == original


@pytest.mark.parametrize(
    "payload",
    [
        '{"suggestions": []}',
        '{"suggestions": [{"title": "", "short_description": "", "estimated_time_minutes": 5}]}',
        '{"suggestions": [{"title": "A", "short_description": "", "estimated_time_minutes": 0}]}',
        '{"suggestions": [{"title": "A", "short_description": "", "estimated_time_minutes": 5,'
        ' "difficulty": "extreme"}]}',
        "not json",
    ],
)
def test_rejects_invalid_suggestions(payload):
    with pytest.raises(ValidationError):
        SuggestionList.model_validate_json(payload)


def test_details_require_steps():
    with pytest.raises(ValidationError):
        RecipeDetails.model_validate(
            {"title": "A", "servings": 2,
             "ingredients": [{"name": "egg", "quantity": "2"}], "steps": []}
        )


def test_strip_code_fences():
    assert strip_code_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert strip_code_fences('{"a": 1}') == '{"a": 1}'
