"""Tests for the repo layer: create / get / list / dedup / quantity parsing."""
from __future__ import annotations

import json
from pathlib import Path

from recetary import db, repo
from recetary.models import IngredientRef, RecipeCreate

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> RecipeCreate:
    return RecipeCreate.model_validate_json((FIXTURES / name).read_text(encoding="utf-8"))


def test_create_and_get_recipe(temp_db):
    payload = _load("polpette.json")
    with db.get_conn() as conn:
        rid = repo.create_recipe(conn, payload)
        recipe = repo.get_recipe(conn, rid)

    assert recipe is not None
    assert recipe.id == rid
    assert recipe.title.startswith("¡Polpette!")
    assert recipe.servings == 2
    assert len(recipe.ingredients) == 9
    assert len(recipe.steps) == 6
    assert recipe.steps[0].step_number == 1
    assert "familia" in recipe.tags

    # quantity parsing should have populated value/unit for "400 gramos"
    patata = next(i for i in recipe.ingredients if i.ingredient.name == "patata")
    assert patata.quantity_value == 400.0
    assert patata.quantity_unit == "g"

    # pantry flag round-trips
    ajo = next(i for i in recipe.ingredients if i.ingredient.name == "ajo")
    assert ajo.is_pantry is True


def test_ingredient_dedup_across_recipes(temp_db):
    a = _load("polpette.json")
    b = RecipeCreate(
        title="Otra receta con tomate",
        ingredients=[
            IngredientRef(name="tomate triturado", category="vegetable", quantity_raw="100 g"),
            IngredientRef(name="ajo", category="seasoning", quantity_raw="2 dientes", is_pantry=True),
        ],
    )
    with db.get_conn() as conn:
        repo.create_recipe(conn, a)
        repo.create_recipe(conn, b)
        ingredients = repo.list_ingredients(conn, limit=200)
    names = [i.name for i in ingredients]
    # No duplicates and case-insensitive uniqueness preserved
    assert names.count("tomate triturado") == 1
    assert names.count("ajo") == 1


def test_list_recipes_returns_summary(temp_db):
    payload = _load("polpette.json")
    with db.get_conn() as conn:
        repo.create_recipe(conn, payload)
        summaries = repo.list_recipes(conn, limit=10)
    assert len(summaries) == 1
    s = summaries[0]
    assert s.title.startswith("¡Polpette!")
    assert s.ingredient_count == 9
    assert "familia" in s.tags


def test_delete_recipe_cascades(temp_db):
    payload = _load("polpette.json")
    with db.get_conn() as conn:
        rid = repo.create_recipe(conn, payload)
    with db.get_conn() as conn:
        assert repo.delete_recipe(conn, rid) is True
    with db.get_conn() as conn:
        assert repo.get_recipe(conn, rid) is None
        # child rows should be gone
        rows = conn.execute(
            "SELECT COUNT(*) AS n FROM recipe_ingredients WHERE recipe_id = ?", (rid,)
        ).fetchone()
        assert rows["n"] == 0


def test_update_recipe_replaces_children(temp_db):
    payload = _load("polpette.json")
    with db.get_conn() as conn:
        rid = repo.create_recipe(conn, payload)

    updated_payload = payload.model_copy(update={
        "title": "Polpette express",
        "ingredients": [
            IngredientRef(name="patata", category="vegetable", quantity_raw="500 g"),
        ],
        "steps": payload.steps[:2],
        "tags": ["express"],
    })
    with db.get_conn() as conn:
        updated = repo.update_recipe(conn, rid, updated_payload)
    assert updated is not None
    assert updated.title == "Polpette express"
    assert len(updated.ingredients) == 1
    assert len(updated.steps) == 2
    assert updated.tags == ["express"]
