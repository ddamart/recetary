"""Database access functions backing the API and CLI."""
from __future__ import annotations

import sqlite3
import uuid
from typing import Optional

from .extraction.video import source_identity
from .models import (
    IngredientOut,
    Recipe,
    RecipeCreate,
    RecipeIngredientOut,
    RecipeSummary,
    StepOut,
)
from .quantities import parse_quantity


class DuplicateSourceError(Exception):
    def __init__(self, recipe_id: str, title: str):
        self.recipe_id = recipe_id
        self.title = title
        super().__init__(f"Source already imported as {title}")


def find_duplicate_source(
    conn: sqlite3.Connection,
    source_ref: Optional[str],
) -> Optional[tuple[str, str]]:
    identity = source_identity(source_ref or "")
    if not identity or identity[0] == "youtube":
        return None
    row = conn.execute(
        "SELECT rs.recipe_id, r.title "
        "FROM recipe_sources rs JOIN recipes r ON r.id = rs.recipe_id "
        "WHERE rs.source_platform = ? AND rs.source_id = ?",
        identity,
    ).fetchone()
    return (row["recipe_id"], row["title"]) if row else None


def _check_duplicate_source(
    conn: sqlite3.Connection,
    source_ref: Optional[str],
) -> None:
    duplicate = find_duplicate_source(conn, source_ref)
    if duplicate:
        raise DuplicateSourceError(*duplicate)


def _register_source(
    conn: sqlite3.Connection,
    recipe_id: str,
    source_ref: Optional[str],
) -> None:
    identity = source_identity(source_ref or "")
    if not identity or identity[0] == "youtube":
        return
    conn.execute(
        "INSERT INTO recipe_sources(source_platform, source_id, recipe_id) VALUES (?, ?, ?)",
        (*identity, recipe_id),
    )


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


def create_recipe(conn: sqlite3.Connection, payload: RecipeCreate) -> str:
    _check_duplicate_source(conn, payload.source_ref)
    recipe_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO recipes (
            id, title, subtitle, description, servings,
            total_time_min, cook_time_min, difficulty, image_path,
            source_type, source_ref, raw_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            recipe_id,
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
                quantity_value, quantity_unit, notes, substitutes, is_pantry
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                recipe_id,
                ingredient_id,
                ing.quantity_raw,
                value,
                unit,
                ing.notes,
                ing.substitutes,
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

    _register_source(conn, recipe_id, payload.source_ref)
    return recipe_id


def _hydrate_recipe(conn: sqlite3.Connection, row: sqlite3.Row) -> Recipe:
    rid = row["id"]
    ingredient_rows = conn.execute(
        """
        SELECT i.id AS ingredient_id, i.name, i.category,
               ri.quantity_raw, ri.quantity_value, ri.quantity_unit,
               ri.notes, ri.substitutes, ri.is_pantry
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
            substitutes=r["substitutes"],
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
        servings=int(row["servings"]) if row["servings"] is not None else None,
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


def get_recipe(conn: sqlite3.Connection, recipe_id: str) -> Optional[Recipe]:
    row = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    return _hydrate_recipe(conn, row) if row else None


def list_recipes(
    conn: sqlite3.Connection,
    *,
    limit: int = 24,
    offset: int = 0,
    tag: Optional[str] = None,
    sort: str = "recent",
) -> list[RecipeSummary]:
    if sort == "alpha":
        order = "r.title COLLATE NOCASE"
    elif sort == "random":
        order = "RANDOM()"
    else:
        order = "r.created_at DESC"
    if tag:
        rows = conn.execute(
            f"""
            SELECT r.id, r.title, r.subtitle, r.image_path, r.total_time_min, r.servings,
                   r.created_at,
                   (SELECT COUNT(*) FROM recipe_ingredients ri WHERE ri.recipe_id = r.id) AS ic
            FROM recipes r
            JOIN tags t ON t.recipe_id = r.id
            WHERE t.tag = ?
            ORDER BY {order}
            LIMIT ? OFFSET ?
            """,
            (tag, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            f"""
            SELECT r.id, r.title, r.subtitle, r.image_path, r.total_time_min, r.servings,
                   r.created_at,
                   (SELECT COUNT(*) FROM recipe_ingredients ri WHERE ri.recipe_id = r.id) AS ic
            FROM recipes r
            ORDER BY {order}
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    summaries: list[RecipeSummary] = []
    for r in rows:
        rid = r["id"]
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
                created_at=r["created_at"],
            )
        )
    return summaries


def delete_recipe(conn: sqlite3.Connection, recipe_id: str) -> bool:
    cursor = conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    return cursor.rowcount > 0


def update_recipe(
    conn: sqlite3.Connection,
    recipe_id: str,
    payload: RecipeCreate,
) -> Optional[Recipe]:
    row = conn.execute("SELECT id FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row:
        return None
    old = conn.execute(
        "SELECT source_ref FROM recipes WHERE id = ?", (recipe_id,)
    ).fetchone()
    old_identity = source_identity(old["source_ref"] or "") if old else None
    new_identity = source_identity(payload.source_ref or "")
    if new_identity != old_identity:
        _check_duplicate_source(conn, payload.source_ref)
        if old_identity and old_identity[0] != "youtube":
            conn.execute(
                "DELETE FROM recipe_sources WHERE source_platform = ? "
                "AND source_id = ? AND recipe_id = ?",
                (*old_identity, recipe_id),
            )
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
            "quantity_value, quantity_unit, notes, substitutes, is_pantry) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (recipe_id, ingredient_id, ing.quantity_raw, value, unit, ing.notes, ing.substitutes, int(ing.is_pantry)),
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
    if new_identity != old_identity:
        _register_source(conn, recipe_id, payload.source_ref)
    return get_recipe(conn, recipe_id)


def count_recipes(conn: sqlite3.Connection) -> int:
    """Return total number of recipes."""
    row = conn.execute("SELECT COUNT(*) AS cnt FROM recipes").fetchone()
    return int(row["cnt"])


def list_tags(conn: sqlite3.Connection) -> list[str]:
    """Return all distinct tags, sorted alphabetically."""
    rows = conn.execute(
        "SELECT DISTINCT tag FROM tags ORDER BY tag"
    ).fetchall()
    return [r["tag"] for r in rows]


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
