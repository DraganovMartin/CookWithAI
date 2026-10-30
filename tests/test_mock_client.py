import pytest

from cookwithai.services.recipe_service import has_expected_mix

PANTRIES = [
    ["eggs"],
    ["eggs", "tomato", "onion", "cheese"],
    ["chicken breast", "rice", "soy sauce", "garlic"],
    ["pasta", "parmesan", "rice", "soy sauce", "garlic", "butter", "tortillas", "lime"],
]


@pytest.mark.parametrize("available", PANTRIES)
def test_suggestions_have_expected_mix(mock_llm, available):
    suggestions = mock_llm.suggest_recipes(available)

    assert len(suggestions) == 3
    assert has_expected_mix(suggestions)
    for suggestion in suggestions:
        assert not set(suggestion.missing_ingredients) & set(available)


def test_suggestions_are_deterministic(mock_llm):
    first = mock_llm.suggest_recipes(["eggs", "tomato"])
    again = mock_llm.suggest_recipes(["eggs", "tomato"])
    reordered = mock_llm.suggest_recipes(["tomato", "eggs"])
    assert first == again
    # Same ingredient set -> same dishes; only the name order in titles follows the input.
    assert [s.estimated_time_minutes for s in first] == [
        s.estimated_time_minutes for s in reordered
    ]
    assert [s.missing_ingredients for s in first] == [s.missing_ingredients for s in reordered]


def test_single_ingredient_title_does_not_repeat(mock_llm):
    for suggestion in mock_llm.suggest_recipes(["eggs"]):
        assert "Eggs & Eggs" not in suggestion.title


def test_details_flag_missing_ingredients(mock_llm):
    available = ["eggs", "tomato", "onion"]
    extended = next(s for s in mock_llm.suggest_recipes(available) if s.missing_ingredients)

    details = mock_llm.get_recipe_details(extended, available)

    assert details.title == extended.title
    assert {i.name for i in details.ingredients if i.is_missing} == set(
        extended.missing_ingredients
    )
    assert {i.name for i in details.ingredients if not i.is_missing} == set(available)
    assert [s.number for s in details.steps] == list(range(1, len(details.steps) + 1))
    assert all("{" not in s.instruction for s in details.steps)
