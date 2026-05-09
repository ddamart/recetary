"""One-time migration: integer recipe IDs → UUID (TEXT) IDs.

Run once:
    python -m recetary.migrate_uuid

What it does:
  1. Creates new tables with TEXT id/recipe_id columns.
  2. Copies every recipe, generating a uuid4 hex id for each.
  3. Copies child rows (recipe_ingredients, steps, utensils, tags) with the new id.
  4. Renames image files in data/images/ to match the new UUIDs.
  5. Rebuilds the FTS5 index.
  6. Swaps old → new tables via ALTER TABLE RENAME.
"""
from __future__ import annotations

import shutil
import sqlite3
import uuid
from pathlib import Path

from . import db

IMAGES_DIR = db.REPO_ROOT / "data" / "images"


def migrate(conn: sqlite3.Connection) -> None:
    # Check if already migrated: if recipes.id is already TEXT UUIDs, skip.
    row = conn.execute("SELECT typeof(id) AS t, id FROM recipes LIMIT 1").fetchone()
    if row and not str(row["id"]).isdigit():
        print("Already migrated — recipe IDs are not integers. Skipping.")
        return

    print("Starting UUID migration...")

    # Build mapping: old int id → new UUID hex
    old_rows = conn.execute("SELECT id FROM recipes").fetchall()
    id_map: dict[int, str] = {}
    for r in old_rows:
        id_map[int(r["id"])] = str(uuid.uuid4())
    print(f"  {len(id_map)} recipes to migrate")

    # --- Create new tables ------------------------------------------------
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS recipes_new (
            id              TEXT PRIMARY KEY,
            title           TEXT NOT NULL,
            subtitle        TEXT,
            description     TEXT,
            servings        INTEGER DEFAULT 2,
            total_time_min  INTEGER,
            cook_time_min   INTEGER,
            difficulty      TEXT CHECK (difficulty IN ('easy','medium','hard')),
            image_path      TEXT,
            source_type     TEXT NOT NULL CHECK (source_type IN ('pdf','image','text','url','video','manual')),
            source_ref      TEXT,
            raw_text        TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS recipe_ingredients_new (
            recipe_id      TEXT NOT NULL,
            ingredient_id  INTEGER NOT NULL,
            quantity_raw   TEXT,
            quantity_value REAL,
            quantity_unit  TEXT,
            notes          TEXT,
            substitutes    TEXT,
            is_pantry      INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (recipe_id, ingredient_id)
        );

        CREATE TABLE IF NOT EXISTS steps_new (
            recipe_id   TEXT NOT NULL,
            step_number INTEGER NOT NULL,
            title       TEXT,
            text        TEXT NOT NULL,
            image_path  TEXT,
            PRIMARY KEY (recipe_id, step_number)
        );

        CREATE TABLE IF NOT EXISTS utensils_new (
            recipe_id TEXT NOT NULL,
            name      TEXT NOT NULL,
            PRIMARY KEY (recipe_id, name)
        );

        CREATE TABLE IF NOT EXISTS tags_new (
            recipe_id TEXT NOT NULL,
            tag       TEXT NOT NULL,
            PRIMARY KEY (recipe_id, tag)
        );
    """)

    # --- Copy data --------------------------------------------------------
    for old_id, new_id in id_map.items():
        # Copy recipe row
        r = conn.execute("SELECT * FROM recipes WHERE id = ?", (old_id,)).fetchone()
        # Update image_path to new UUID filename
        old_img = r["image_path"]
        new_img = None
        if old_img:
            ext = Path(old_img).suffix or ".png"
            new_img = f"{new_id}{ext}"

        conn.execute(
            """INSERT INTO recipes_new (
                id, title, subtitle, description, servings,
                total_time_min, cook_time_min, difficulty, image_path,
                source_type, source_ref, raw_text, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_id, r["title"], r["subtitle"], r["description"],
                r["servings"], r["total_time_min"], r["cook_time_min"],
                r["difficulty"], new_img,
                r["source_type"], r["source_ref"], r["raw_text"], r["created_at"],
            ),
        )

        # Copy child rows
        for ri in conn.execute(
            "SELECT * FROM recipe_ingredients WHERE recipe_id = ?", (old_id,)
        ):
            conn.execute(
                "INSERT INTO recipe_ingredients_new VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (new_id, ri["ingredient_id"], ri["quantity_raw"],
                 ri["quantity_value"], ri["quantity_unit"],
                 ri["notes"], ri["substitutes"], ri["is_pantry"]),
            )

        for s in conn.execute(
            "SELECT * FROM steps WHERE recipe_id = ?", (old_id,)
        ):
            conn.execute(
                "INSERT INTO steps_new VALUES (?, ?, ?, ?, ?)",
                (new_id, s["step_number"], s["title"], s["text"], s["image_path"]),
            )

        for u in conn.execute(
            "SELECT * FROM utensils WHERE recipe_id = ?", (old_id,)
        ):
            conn.execute(
                "INSERT INTO utensils_new VALUES (?, ?)",
                (new_id, u["name"]),
            )

        for t in conn.execute(
            "SELECT * FROM tags WHERE recipe_id = ?", (old_id,)
        ):
            conn.execute(
                "INSERT INTO tags_new VALUES (?, ?)",
                (new_id, t["tag"]),
            )

    # --- Rename image files -----------------------------------------------
    if IMAGES_DIR.exists():
        renamed = 0
        for old_id, new_id in id_map.items():
            old_r = conn.execute(
                "SELECT image_path FROM recipes WHERE id = ?", (old_id,)
            ).fetchone()
            if not old_r or not old_r["image_path"]:
                continue
            old_file = IMAGES_DIR / old_r["image_path"]
            if old_file.exists():
                ext = old_file.suffix or ".png"
                new_file = IMAGES_DIR / f"{new_id}{ext}"
                shutil.move(str(old_file), str(new_file))
                renamed += 1
        print(f"  Renamed {renamed} image files")

    # --- Drop old tables, rename new ones ---------------------------------
    # Drop FTS first (depends on recipes)
    conn.executescript("""
        DROP TRIGGER IF EXISTS recipes_ai;
        DROP TRIGGER IF EXISTS recipes_ad;
        DROP TRIGGER IF EXISTS recipes_au;
        DROP TABLE IF EXISTS recipes_fts;
    """)

    conn.executescript("""
        DROP TABLE IF EXISTS tags;
        DROP TABLE IF EXISTS utensils;
        DROP TABLE IF EXISTS steps;
        DROP TABLE IF EXISTS recipe_ingredients;
        DROP TABLE IF EXISTS recipes;

        ALTER TABLE recipes_new RENAME TO recipes;
        ALTER TABLE recipe_ingredients_new RENAME TO recipe_ingredients;
        ALTER TABLE steps_new RENAME TO steps;
        ALTER TABLE utensils_new RENAME TO utensils;
        ALTER TABLE tags_new RENAME TO tags;
    """)

    # --- Recreate indexes and FKs ----------------------------------------
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_ingredient
            ON recipe_ingredients(ingredient_id);
        CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);
    """)

    # --- Rebuild FTS5 -----------------------------------------------------
    conn.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS recipes_fts USING fts5(
            title, subtitle, description,
            content='recipes', content_rowid='rowid',
            tokenize="unicode61 remove_diacritics 2"
        );

        CREATE TRIGGER IF NOT EXISTS recipes_ai AFTER INSERT ON recipes BEGIN
            INSERT INTO recipes_fts(rowid, title, subtitle, description)
            VALUES (new.rowid, new.title, new.subtitle, new.description);
        END;

        CREATE TRIGGER IF NOT EXISTS recipes_ad AFTER DELETE ON recipes BEGIN
            INSERT INTO recipes_fts(recipes_fts, rowid, title, subtitle, description)
            VALUES ('delete', old.rowid, old.title, old.subtitle, old.description);
        END;

        CREATE TRIGGER IF NOT EXISTS recipes_au AFTER UPDATE ON recipes BEGIN
            INSERT INTO recipes_fts(recipes_fts, rowid, title, subtitle, description)
            VALUES ('delete', old.rowid, old.title, old.subtitle, old.description);
            INSERT INTO recipes_fts(rowid, title, subtitle, description)
            VALUES (new.rowid, new.title, new.subtitle, new.description);
        END;
    """)

    # Populate FTS from existing recipes
    conn.execute("""
        INSERT INTO recipes_fts(rowid, title, subtitle, description)
        SELECT rowid, title, COALESCE(subtitle, ''), COALESCE(description, '')
        FROM recipes
    """)

    print("  Migration complete!")


def main() -> None:
    path = db.db_path()
    if not path.exists():
        print(f"Database not found at {path}")
        return

    # Back up the database first
    backup = path.with_suffix(".db.bak")
    shutil.copy2(path, backup)
    print(f"Backup saved to {backup}")

    conn = db.connect(path)
    try:
        migrate(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
