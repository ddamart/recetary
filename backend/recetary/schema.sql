-- Canonical, deduplicated ingredients.
-- name stores Spanish content (e.g. "cebolla"); category is an English enum.
CREATE TABLE IF NOT EXISTS ingredients (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    category     TEXT NOT NULL CHECK (category IN (
        'protein','vegetable','legume','fruit','grain',
        'dairy','fat','seasoning','sauce','beverage',
        'nut','other'
    )),
    aliases_json TEXT
);

CREATE TABLE IF NOT EXISTS recipes (
    id              INTEGER PRIMARY KEY,
    title           TEXT NOT NULL,
    subtitle        TEXT,
    description     TEXT,
    servings        INTEGER NOT NULL DEFAULT 2,
    total_time_min  INTEGER,
    cook_time_min   INTEGER,
    difficulty      TEXT CHECK (difficulty IN ('easy','medium','hard')),
    image_path      TEXT,
    source_type     TEXT NOT NULL CHECK (source_type IN ('pdf','image','text','url','manual')),
    source_ref      TEXT,
    raw_text        TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recipe_ingredients (
    recipe_id      INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    ingredient_id  INTEGER NOT NULL REFERENCES ingredients(id),
    quantity_raw   TEXT,
    quantity_value REAL,
    quantity_unit  TEXT,
    notes          TEXT,
    is_pantry      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (recipe_id, ingredient_id)
);

CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_ingredient
    ON recipe_ingredients(ingredient_id);

CREATE TABLE IF NOT EXISTS steps (
    recipe_id   INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,
    title       TEXT,
    text        TEXT NOT NULL,
    image_path  TEXT,
    PRIMARY KEY (recipe_id, step_number)
);

CREATE TABLE IF NOT EXISTS utensils (
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    name      TEXT NOT NULL,
    PRIMARY KEY (recipe_id, name)
);

CREATE TABLE IF NOT EXISTS tags (
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    tag       TEXT NOT NULL,
    PRIMARY KEY (recipe_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);

-- Full-text search over recipe metadata.
CREATE VIRTUAL TABLE IF NOT EXISTS recipes_fts USING fts5(
    title, subtitle, description,
    content='recipes', content_rowid='id',
    tokenize="unicode61 remove_diacritics 2"
);

CREATE TRIGGER IF NOT EXISTS recipes_ai AFTER INSERT ON recipes BEGIN
    INSERT INTO recipes_fts(rowid, title, subtitle, description)
    VALUES (new.id, new.title, new.subtitle, new.description);
END;

CREATE TRIGGER IF NOT EXISTS recipes_ad AFTER DELETE ON recipes BEGIN
    INSERT INTO recipes_fts(recipes_fts, rowid, title, subtitle, description)
    VALUES ('delete', old.id, old.title, old.subtitle, old.description);
END;

CREATE TRIGGER IF NOT EXISTS recipes_au AFTER UPDATE ON recipes BEGIN
    INSERT INTO recipes_fts(recipes_fts, rowid, title, subtitle, description)
    VALUES ('delete', old.id, old.title, old.subtitle, old.description);
    INSERT INTO recipes_fts(rowid, title, subtitle, description)
    VALUES (new.id, new.title, new.subtitle, new.description);
END;

-- Typo-tolerant matching is implemented in Python (rapidfuzz) on top of these
-- tables; no spellfix1 virtual tables are needed.
