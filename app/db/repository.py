"""Data access for recipe searches. Works with plain dicts/lists; JSON columns are (de)serialised here."""

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RecipeRecord:
    id: int
    user_id: int
    created_at: str
    available_ingredients: list[str]
    suggested_recipes: list[dict[str, Any]]
    chosen_recipe: str | None = None
    steps: dict[str, Any] | None = None
    missing_ingredients: list[str] = field(default_factory=list)


_SELECT_RECIPE = """
    SELECT r.id, r.user_id, r.created_at, r.suggested_recipes, r.chosen_recipe, r.steps,
           i.available_ingredients, i.missing_ingredients
    FROM recipes r
    JOIN ingredients i ON i.recipe_id = r.id
"""


def _to_record(row: sqlite3.Row) -> RecipeRecord:
    return RecipeRecord(
        id=row["id"],
        user_id=row["user_id"],
        created_at=row["created_at"],
        available_ingredients=json.loads(row["available_ingredients"]),
        suggested_recipes=json.loads(row["suggested_recipes"]),
        chosen_recipe=row["chosen_recipe"],
        steps=json.loads(row["steps"]) if row["steps"] else None,
        missing_ingredients=json.loads(row["missing_ingredients"]),
    )


def create_recipe_request(
    conn: sqlite3.Connection,
    user_id: int,
    available_ingredients: list[str],
    suggested_recipes: list[dict[str, Any]],
) -> int:
    """Store a new search (its suggestions + the user's ingredients) and return the recipe id."""
    cursor = conn.execute(
        "INSERT INTO recipes (user_id, suggested_recipes) VALUES (?, ?)",
        (user_id, json.dumps(suggested_recipes)),
    )
    recipe_id = cursor.lastrowid
    conn.execute(
        "INSERT INTO ingredients (recipe_id, available_ingredients) VALUES (?, ?)",
        (recipe_id, json.dumps(available_ingredients)),
    )
    return recipe_id


def save_chosen_recipe(
    conn: sqlite3.Connection,
    recipe_id: int,
    chosen_recipe: str,
    steps: dict[str, Any],
    missing_ingredients: list[str],
) -> None:
    cursor = conn.execute(
        "UPDATE recipes SET chosen_recipe = ?, steps = ? WHERE id = ?",
        (chosen_recipe, json.dumps(steps), recipe_id),
    )
    if cursor.rowcount == 0:
        raise LookupError(f"Recipe {recipe_id} not found")
    conn.execute(
        "UPDATE ingredients SET missing_ingredients = ? WHERE recipe_id = ?",
        (json.dumps(missing_ingredients), recipe_id),
    )


def get_recipe(conn: sqlite3.Connection, recipe_id: int) -> RecipeRecord | None:
    row = conn.execute(_SELECT_RECIPE + " WHERE r.id = ?", (recipe_id,)).fetchone()
    return _to_record(row) if row else None


def list_recent(conn: sqlite3.Connection, user_id: int, limit: int = 10) -> list[RecipeRecord]:
    rows = conn.execute(
        _SELECT_RECIPE + " WHERE r.user_id = ? ORDER BY r.created_at DESC, r.id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return [_to_record(row) for row in rows]
