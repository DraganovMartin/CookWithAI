import logging

import pytest

from cookwithai.db.database import connect
from cookwithai.llm.schemas import RecipeSuggestion
from cookwithai.services.recipe_service import (
    RecipeService,
    has_expected_mix,
    normalize_ingredients,
)


def _suggestion(missing):
    return RecipeSuggestion(
        title="X", short_description="", missing_ingredients=missing, estimated_time_minutes=5
    )


def test_normalize_ingredients():
    assert normalize_ingredients(["  Eggs ", "eggs", "", "Bell   Pepper", "tomato"]) == [
        "eggs",
        "bell pepper",
        "tomato",
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
        RecipeService(AllCompleteLLM(), db_path, None).suggest(["eggs"])
    assert "Unexpected suggestion mix" in caplog.text


def test_guest_search_writes_nothing(guest_service, db_path):
    session = guest_service.suggest(["eggs", "tomato"])
    guest_service.choose(session, session.suggestions[0])

    assert session.recipe_id is None
    assert session.details is not None
    assert guest_service.history() == []
    with connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM recipes").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM ingredients").fetchone()[0] == 0


def test_guest_cannot_load_saved_recipes(service, guest_service):
    session = service.suggest(["eggs"])
    assert guest_service.load(session.recipe_id) is None


def test_users_only_see_their_own_recipes(mock_llm, db_path, auth):
    alice = auth.register("alice@example.com", "password-1")
    bob = auth.register("bob@example.com", "password-2")
    alice_service = RecipeService(mock_llm, db_path, alice.id)
    bob_service = RecipeService(mock_llm, db_path, bob.id)

    session = alice_service.suggest(["eggs"])

    assert [s.recipe_id for s in alice_service.history()] == [session.recipe_id]
    assert bob_service.history() == []
    assert bob_service.load(session.recipe_id) is None
