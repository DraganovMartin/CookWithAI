import sqlite3

import pytest

from app.db import repository
from app.db.database import GUEST_USER_ID, connect, init_db

SUGGESTIONS = [{"title": "Omelette"}, {"title": "Shakshuka", "missing_ingredients": ["cumin"]}]


def test_init_db_is_idempotent_and_seeds_guest(db_path):
    init_db(db_path)
    with connect(db_path) as conn:
        users = conn.execute("SELECT id, display_name FROM users").fetchall()
    assert [tuple(u) for u in users] == [(GUEST_USER_ID, "Guest")]


def test_init_db_migrates_a_database_from_before_accounts(tmp_path):
    path = str(tmp_path / "old.db")
    with connect(path) as conn:
        conn.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE,"
            " display_name TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        conn.execute("INSERT INTO users (id, display_name) VALUES (?, ?)", (GUEST_USER_ID, "Guest"))

    init_db(path)
    init_db(path)

    with connect(path) as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        guest = conn.execute("SELECT display_name FROM users").fetchall()
    assert {"password_hash", "session_id", "login_timestamp", "session_time"} <= columns
    assert [tuple(row) for row in guest] == [("Guest",)]


def test_create_then_choose_round_trip(db_path):
    with connect(db_path) as conn:
        recipe_id = repository.create_recipe_request(conn, GUEST_USER_ID, ["eggs"], SUGGESTIONS)

    with connect(db_path) as conn:
        fresh = repository.get_recipe(conn, recipe_id)
    assert fresh.available_ingredients == ["eggs"]
    assert fresh.suggested_recipes == SUGGESTIONS
    assert fresh.chosen_recipe is None and fresh.steps is None
    assert fresh.missing_ingredients == []

    with connect(db_path) as conn:
        repository.save_chosen_recipe(conn, recipe_id, "Shakshuka", {"steps": [1]}, ["cumin"])
        chosen = repository.get_recipe(conn, recipe_id)
    assert chosen.chosen_recipe == "Shakshuka"
    assert chosen.steps == {"steps": [1]}
    assert chosen.missing_ingredients == ["cumin"]


def test_save_chosen_recipe_unknown_id(db_path):
    with connect(db_path) as conn, pytest.raises(LookupError):
        repository.save_chosen_recipe(conn, 999, "X", {}, [])


def test_list_recent_newest_first(db_path):
    with connect(db_path) as conn:
        ids = [
            repository.create_recipe_request(conn, GUEST_USER_ID, [name], SUGGESTIONS)
            for name in ("a", "b", "c")
        ]
        recent = repository.list_recent(conn, GUEST_USER_ID, limit=2)
    assert [r.id for r in recent] == [ids[2], ids[1]]


def test_foreign_keys_enforced(db_path):
    with connect(db_path) as conn, pytest.raises(sqlite3.IntegrityError):
        repository.create_recipe_request(conn, 42, ["eggs"], SUGGESTIONS)


def test_deleting_recipe_cascades_to_ingredients(db_path):
    with connect(db_path) as conn:
        recipe_id = repository.create_recipe_request(conn, GUEST_USER_ID, ["eggs"], SUGGESTIONS)
        conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        remaining = conn.execute("SELECT COUNT(*) FROM ingredients").fetchone()[0]
    assert remaining == 0
