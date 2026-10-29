import logging

import pytest

from app.llm.schemas import RecipeSuggestion
from app.services.recipe_service import RecipeService, has_expected_mix, normalize_ingredients


def _suggestion(missing):
    return RecipeSuggestion(
        title="X", short_description="", missing_ingredients=missing, estimated_time_minutes=5
    )


def test_normalize_ingredients():
    assert normalize_ingredients(["  Eggs ", "eggs", "", "Bell   Pepper", "tomato"]) == [
        "eggs", "bell pepper", "tomato",
    ]


@pytest.mark.parametrize(
    ("missing_lists", "expected"),
    [
        ([[], [], ["a"]], True),
        ([[], ["a"], ["b"]], True),
        ([[], [], []], False),
        ([["a"], ["b"], ["c"]], False),
    ],
)
def test_has_expected_mix(missing_lists, expected):
    assert has_expected_mix([_suggestion(m) for m in missing_lists]) is expected


def test_suggest_rejects_empty_input(service):
    with pytest.raises(ValueError):
        service.suggest(["  ", ""])


def test_suggest_choose_and_history(service):
    session = service.suggest(["Eggs", "tomato", "onion"])
    assert session.available_ingredients == ["eggs", "tomato", "onion"]
    assert len(session.suggestions) == 3

    extended = next(s for s in session.suggestions if s.missing_ingredients)
    details = service.choose(session, extended)
    assert session.details == details

    [past] = service.history()
    assert past.recipe_id == session.recipe_id
    assert past.suggestions == session.suggestions
    assert past.details == details

    loaded = service.load(session.recipe_id)
    assert loaded.details.title == extended.title


def test_load_unknown_recipe(service):
    assert service.load(12345) is None


def test_warns_on_unexpected_mix(db_path, caplog):
    class AllCompleteLLM:
        def suggest_recipes(self, available):
            return [_suggestion([]) for _ in range(3)]

    with caplog.at_level(logging.WARNING):
        RecipeService(AllCompleteLLM(), db_path).suggest(["eggs"])
    assert "Unexpected suggestion mix" in caplog.text
