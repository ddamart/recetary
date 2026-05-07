"""Database access functions backing the API and CLI."""
from __future__ import annotations

import sqlite3
from typing import Optional

from .models import (
    IngredientOut,
    Recipe,
    RecipeCreate,
    RecipeIngredientOut,
    RecipeSummary,
    StepOut,
)
from .quantities import parse_quantity


def upsert_ingredient(conn: sqlite3.Connection, name: str, category: str) -> int:
    """Return the id of an ingredient, inserting if missing.

    Lookup is case-insensitive (the column uses COLLATE NOCASE).
    """
    name = name.strip()
    row = conn.execute(
        "SELECT id FROM ingredients WHERE name = ?", (name,)
    ).fetchone()
    if row:
        return int(row["id"])
    cursor = conn.execute(
        "INSERT INTO ingredients(name, category) VALUES (?, ?)",
        (name, category),
    )
    return int(cursor.lastrowid)


def create_recipe(conn: sqlite3.Connection, payload: RecipeCreate) -> int:
    cursor = conn.execute(
        """
        INSERT INTO recipes (
            title, subtitle, description, servings,
            total_time_min, cook_time_min, difficulty, image_path,
            source_type, source_ref, raw_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.title,
            payload.subtitle,
            payload.description,
            payload.servings,
            payload.total_time_min,
            payload.cook_time_min,
            payload.difficulty,
            payload.image_path,
            payload.source_type,
            payload.source_ref,
            payload.raw_text,
        ),
    )
    recipe_id = int(cursor.lastrowid)

    # Deduplicate ingredients by canonical name within this recipe.
    seen: set[int] = set()
    for ing in payload.ingredients:
        ingredient_id = upsert_ingredient(conn, ing.name, ing.category)
        if ingredient_id in seen:
            continue
        seen.add(ingredient_id)
        value = ing.quantity_value
        unit = ing.quantity_unit
        if value is None and unit is None and ing.quantity_raw:
            value, unit = parse_quantity(ing.quantity_raw)
        conn.execute(
            """
            INSERT INTO recipe_ingredients (
                recipe_id, ingredient_id, quantity_raw,
                quantity_value, quantity_unit, notes, is_pantry
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                recipe_id,
                ingredient_id,
                ing.quantity_raw,
                value,
                unit,
                ing.notes,
                int(ing.is_pantry),
            ),
        )

    for index, step in enumerate(payload.steps, start=1):
        conn.execute(
            "INSERT INTO steps(recipe_id, step_number, title, text, image_path) "
            "VALUES (?, ?, ?, ?, ?)",
            (recipe_id, index, step.title, step.text, step.image_path),
        )

    for utensil in dict.fromkeys(u.strip() for u in payload.utensils if u.strip()):
        conn.execute(
            "INSERT OR IGNORE INTO utensils(recipe_id, name) VALUES (?, ?)",
            (recipe_id, utensil),
        )

    for tag in dict.fromkeys(t.strip() for t in payload.tags if t.strip()):
        conn.execute(
            "INSERT OR IGNORE INTO tags(recipe_id, tag) VALUES (?, ?)",
            (recipe_id, tag),
        )

    return recipe_id


def _hydrate_recipe(conn: sqlite3.Connection, row: sqlite3.Row) -> Recipe:
    rid = int(row["id"])
    ingredient_rows = conn.execute(
        """
        SELECT i.id AS ingredient_id, i.name, i.category,
               ri.quantity_raw, ri.quantity_value, ri.quantity_unit,
               ri.notes, ri.is_pantry
        FROM recipe_ingredients ri
        JOIN ingredients i ON i.id = ri.ingredient_id
        WHERE ri.recipe_id = ?
        ORDER BY ri.is_pantry, i.name
        """,
        (rid,),
    ).fetchall()
    ingredients = [
        RecipeIngredientOut(
            ingredient=IngredientOut(
                id=int(r["ingredient_id"]),
                name=r["name"],
                category=r["category"],
            ),
            quantity_raw=r["quantity_raw"],
            quantity_value=r["quantity_value"],
            quantity_unit=r["quantity_unit"],
            notes=r["notes"],
            is_pantry=bool(r["is_pantry"]),
        )
        for r in ingredient_rows
    ]

    step_rows = conn.execute(
        "SELECT step_number, title, text, image_path FROM steps "
        "WHERE recipe_id = ? ORDER BY step_number",
        (rid,),
    ).fetchall()
    steps = [
        StepOut(
            step_number=int(s["step_number"]),
            title=s["title"],
            text=s["text"],
            image_path=s["image_path"],
        )
        for s in step_rows
    ]

    utensils = [
        r["name"]
        for r in conn.execute(
            "SELECT name FROM utensils WHERE recipe_id = ? ORDER BY name", (rid,)
        )
    ]
    tags = [
        r["tag"]
        for r in conn.execute(
            "SELECT tag FROM tags WHERE recipe_id = ? ORDER BY tag", (rid,)
        )
    ]

    return Recipe(
        id=rid,
        title=row["title"],
        subtitle=row["subtitle"],
        description=row["description"],
        servings=int(row["servings"]),
        total_time_min=row["total_time_min"],
        cook_time_min=row["cook_time_min"],
        difficulty=row["difficulty"],
        image_path=row["image_path"],
        source_type=row["source_type"],
        source_ref=row["source_ref"],
        created_at=row["created_at"],
        ingredients=ingredients,
        steps=steps,
        utensils=utensils,
        tags=tags,
    )


def get_recipe(conn: sqlite3.Connection, recipe_id: int) -> Optional[Recipe]:
    row = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    return _hydrate_recipe(conn, row) if row else None


def list_recipes(
    conn: sqlite3.Connection,
    *,
    limit: int = 24,
    offset: int = 0,
    tag: Optional[str] = None,
) -> list[RecipeSummary]:
    if tag:
        rows = conn.execute(
            """
            SELECT r.id, r.title, r.subtitle, r.image_path, r.total_time_min, r.servings,
                   (SELECT COUNT(*) FROM recipe_ingredients ri WHERE ri.recipe_id = r.id) AS ic
            FROM recipes r
            JOIN tags t ON t.recipe_id = r.id
            WHERE t.tag = ?
            ORDER BY r.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (tag, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT r.id, r.title, r.subtitle, r.image_path, r.total_time_min, r.servings,
                   (SELECT COUNT(*) FROM recipe_ingredients ri WHERE ri.recipe_id = r.id) AS ic
            FROM recipes r
            ORDER BY r.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    summaries: list[RecipeSummary] = []
    for r in rows:
        rid = int(r["id"])
        tags = [
            row["tag"]
            for row in conn.execute(
                "SELECT tag FROM tags WHERE recipe_id = ? ORDER BY tag", (rid,)
            )
        ]
        summaries.append(
            RecipeSummary(
                id=rid,
                title=r["title"],
                subtitle=r["subtitle"],
                image_path=r["image_path"],
                total_time_min=r["total_time_min"],
                servings=int(r["servings"]),
                ingredient_count=int(r["ic"]),
                tags=tags,
            )
        )
    return summaries


def delete_recipe(conn: sqlite3.Connection, recipe_id: int) -> bool:
    cursor = conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    return cursor.rowcount > 0


def update_recipe(
    conn: sqlite3.Connection,
    recipe_id: int,
    payload: RecipeCreate,
) -> Optional[Recipe]:
    row = conn.execute("SELECT id FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row:
        return None
    conn.execute(
        """
        UPDATE recipes SET
            title = ?, subtitle = ?, description = ?, servings = ?,
            total_time_min = ?, cook_time_min = ?, difficulty = ?, image_path = ?,
            source_type = ?, source_ref = ?, raw_text = ?
        WHERE id = ?
        """,
        (
            payload.title,
            payload.subtitle,
            payload.description,
            payload.servings,
            payload.total_time_min,
            payload.cook_time_min,
            payload.difficulty,
            payload.image_path,
            payload.source_type,
            payload.source_ref,
            payload.raw_text,
            recipe_id,
        ),
    )
    # Replace child rows wholesale.
    conn.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
    conn.execute("DELETE FROM steps WHERE recipe_id = ?", (recipe_id,))
    conn.execute("DELETE FROM utensils WHERE recipe_id = ?", (recipe_id,))
    conn.execute("DELETE FROM tags WHERE recipe_id = ?", (recipe_id,))
    seen: set[int] = set()
    for ing in payload.ingredients:
        ingredient_id = upsert_ingredient(conn, ing.name, ing.category)
        if ingredient_id in seen:
            continue
        seen.add(ingredient_id)
        value = ing.quantity_value
        unit = ing.quantity_unit
        if value is None and unit is None and ing.quantity_raw:
            value, unit = parse_quantity(ing.quantity_raw)
        conn.execute(
            "INSERT INTO recipe_ingredients(recipe_id, ingredient_id, quantity_raw, "
            "quantity_value, quantity_unit, notes, is_pantry) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (recipe_id, ingredient_id, ing.quantity_raw, value, unit, ing.notes, int(ing.is_pantry)),
        )
    for index, step in enumerate(payload.steps, start=1):
        conn.execute(
            "INSERT INTO steps(recipe_id, step_number, title, text, image_path) "
            "VALUES (?, ?, ?, ?, ?)",
            (recipe_id, index, step.title, step.text, step.image_path),
        )
    for utensil in dict.fromkeys(u.strip() for u in payload.utensils if u.strip()):
        conn.execute(
            "INSERT OR IGNORE INTO utensils(recipe_id, name) VALUES (?, ?)",
            (recipe_id, utensil),
        )
    for tag in dict.fromkeys(t.strip() for t in payload.tags if t.strip()):
        conn.execute(
            "INSERT OR IGNORE INTO tags(recipe_id, tag) VALUES (?, ?)",
            (recipe_id, tag),
        )
    return get_recipe(conn, recipe_id)


def list_ingredients(
    conn: sqlite3.Connection,
    *,
    query: Optional[str] = None,
    limit: int = 50,
) -> list[IngredientOut]:
    if query:
        rows = conn.execute(
            "SELECT id, name, category FROM ingredients "
            "WHERE name LIKE ? COLLATE NOCASE ORDER BY name LIMIT ?",
            (f"%{query.strip()}%", limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, name, category FROM ingredients ORDER BY name LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        IngredientOut(id=int(r["id"]), name=r["name"], category=r["category"])
        for r in rows
    ]
