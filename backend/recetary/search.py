"""Recipe search: title FTS5 + ingredient intersection with fuzzy resolution.

Three search modes share one entry point:

  * `q="albondiga"`             → fuzzy title (FTS5 + diacritic-insensitive).
  * `ingredients=["cebolla", "tomate"]` → strict intersection on canonical
    ingredients (each token resolved fuzzily to the closest existing canonical
    ingredient via rapidfuzz).
  * Both                        → intersection filter, then ordered by FTS bm25.

Random recipe shares the ingredient/tag filter and adds `ORDER BY RANDOM()`.
"""
from __future__ import annotations

import sqlite3
import unicodedata
from typing import Iterable, Optional

from rapidfuzz import fuzz, process

from .models import RecipeMatch


# Minimum normalized score (0–100) for accepting a fuzzy ingredient match.
INGREDIENT_FUZZY_THRESHOLD = 75
# How aggressive the title fallback is when FTS finds nothing.
TITLE_FUZZY_THRESHOLD = 70


def _strip(s: str) -> str:
    return s.strip().lower()


def _all_ingredient_names(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    return [
        (int(r["id"]), r["name"])
        for r in conn.execute("SELECT id, name FROM ingredients")
    ]


def resolve_ingredient(
    conn: sqlite3.Connection, query: str
) -> Optional[tuple[int, str, int]]:
    """Map an ingredient query to its single best canonical (id, name, score).

    Used for autocomplete and the legacy single-match path. Returns None when
    no canonical ingredient scores above the threshold.
    """
    query = _strip(query)
    if not query:
        return None
    pool = _all_ingredient_names(conn)
    if not pool:
        return None
    for ing_id, name in pool:
        if name.lower() == query:
            return ing_id, name, 100
    choices = {ing_id: name for ing_id, name in pool}
    match = process.extractOne(
        query,
        choices,
        scorer=fuzz.WRatio,
        score_cutoff=INGREDIENT_FUZZY_THRESHOLD,
    )
    if not match:
        return None
    name, score, ing_id = match
    return int(ing_id), str(name), int(score)


def _resolve_token_to_group(
    conn: sqlite3.Connection, query: str
) -> list[tuple[int, str]]:
    """Resolve one user token to *all* canonical ingredients that match it.

    A canonical name matches when:
      * the query is a substring of the canonical name (or vice versa) — e.g.
        "pollo" matches "pechuga de pollo", "muslo de pollo deshuesado".
      * the query fuzzy-matches the canonical name above the threshold —
        catches typos like "tomte" → "tomate".

    This is the semantic users expect: "I have pollo" matches any chicken cut.
    """
    query_lower = _strip(query)
    if not query_lower:
        return []
    pool = _all_ingredient_names(conn)
    matched: list[tuple[int, str]] = []
    for ing_id, name in pool:
        name_lower = name.lower()
        if query_lower in name_lower or name_lower in query_lower:
            matched.append((ing_id, name))
            continue
        if fuzz.WRatio(query_lower, name_lower) >= INGREDIENT_FUZZY_THRESHOLD:
            matched.append((ing_id, name))
    return matched


def _filter_recipe_ids_by_groups(
    conn: sqlite3.Connection, groups: list[set[int]]
) -> list[int]:
    """Return recipe ids that contain ≥1 ingredient from EACH group."""
    if not groups:
        return []
    universe: set[int] = set().union(*groups)
    if not universe:
        return []
    placeholders = ",".join("?" * len(universe))
    rows = conn.execute(
        f"SELECT recipe_id, ingredient_id FROM recipe_ingredients "
        f"WHERE ingredient_id IN ({placeholders})",
        tuple(universe),
    ).fetchall()
    by_recipe: dict[int, set[int]] = {}
    for r in rows:
        by_recipe.setdefault(int(r["recipe_id"]), set()).add(int(r["ingredient_id"]))
    return [rid for rid, ings in by_recipe.items() if all(g & ings for g in groups)]


def _fts_query(q: str) -> str:
    """Sanitize a free-text query for FTS5 MATCH. Adds prefix wildcards per token."""
    tokens = [t for t in q.replace('"', " ").split() if t]
    if not tokens:
        return ""
    return " ".join(f"{t}*" for t in tokens)


def _strip_diacritics(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _like_match_ids(conn: sqlite3.Connection, q: str) -> list[int]:
    """SQL LIKE substring match on title, subtitle, and description.

    Uses strip_diacritics() so 'asiatica' matches 'asiática'.
    Also tries gender-stem variants ('asiatica' → 'asiatic%') so that
    masculine/feminine/plural forms all match.
    Slower than FTS5 (table scan) but catches infix matches like
    "soba" inside "Yakisoba".  Instant for hundreds of recipes.
    """
    clean = _strip_diacritics(q.strip().lower())
    patterns = [f"%{clean}%"]
    # Add gender-stem variant: strip trailing a/o/as/os to get a common root
    for suffix in ("as", "os", "a", "o"):
        if clean.endswith(suffix) and len(clean) > len(suffix) + 2:
            stem = clean[: -len(suffix)]
            patterns.append(f"%{stem}%")
            break
    # Build OR conditions for all patterns
    conditions = " OR ".join(
        "(LOWER(strip_diacritics(title)) LIKE ? "
        "OR LOWER(strip_diacritics(COALESCE(subtitle, ''))) LIKE ? "
        "OR LOWER(strip_diacritics(COALESCE(description, ''))) LIKE ?)"
        for _ in patterns
    )
    params = tuple(p for pat in patterns for p in (pat, pat, pat))
    rows = conn.execute(
        f"SELECT id FROM recipes WHERE {conditions} ORDER BY created_at DESC",
        params,
    ).fetchall()
    return [int(r["id"]) for r in rows]


def _title_match_ids(conn: sqlite3.Connection, q: str) -> list[int]:
    """Tier 1 FTS5 prefix + LIKE union → Tier 2 fuzzy fallback."""
    result_ids: list[int] = []
    seen: set[int] = set()

    # Tier 1a: FTS5 prefix (fast, BM25-ranked) — best relevance ordering
    fts = _fts_query(q)
    if fts:
        rows = conn.execute(
            "SELECT rowid FROM recipes_fts WHERE recipes_fts MATCH ? ORDER BY bm25(recipes_fts)",
            (fts,),
        ).fetchall()
        for r in rows:
            rid = int(r["rowid"])
            if rid not in seen:
                seen.add(rid)
                result_ids.append(rid)

    # Tier 1b: LIKE substring — catches infix and gender/plural variants
    like_ids = _like_match_ids(conn, q)
    for rid in like_ids:
        if rid not in seen:
            seen.add(rid)
            result_ids.append(rid)

    if result_ids:
        return result_ids

    # Tier 2: rapidfuzz fallback for typo correction
    candidates = conn.execute(
        "SELECT id, title || ' ' || COALESCE(subtitle, '') AS hay FROM recipes"
    ).fetchall()
    if not candidates:
        return []
    scored = process.extract(
        q,
        {int(r["id"]): r["hay"] for r in candidates},
        scorer=fuzz.partial_ratio,
        score_cutoff=TITLE_FUZZY_THRESHOLD,
        limit=50,
    )
    return [int(rid) for _name, _score, rid in scored]


def search_recipes(
    conn: sqlite3.Connection,
    *,
    q: Optional[str] = None,
    ingredients: Optional[list[str]] = None,
    tag: Optional[str] = None,
    sort: str = "recent",
    limit: int = 24,
    offset: int = 0,
) -> list[RecipeMatch]:
    """Return matching recipes, ordered by relevance / recency / title."""
    ingredients = [i for i in (ingredients or []) if i and i.strip()]

    groups: list[set[int]] = []
    matched_names: list[str] = []
    if ingredients:
        for token in ingredients:
            group = _resolve_token_to_group(conn, token)
            if not group:
                return []
            groups.append({pair[0] for pair in group})
            matched_names.append(token.strip().lower())

    candidate_ids: Optional[set[int]] = None
    if groups:
        candidate_ids = set(_filter_recipe_ids_by_groups(conn, groups))
        if not candidate_ids:
            return []

    if tag:
        rows = conn.execute(
            "SELECT recipe_id FROM tags WHERE tag = ?", (tag,)
        ).fetchall()
        tag_ids = {int(r["recipe_id"]) for r in rows}
        candidate_ids = tag_ids if candidate_ids is None else candidate_ids & tag_ids
        if not candidate_ids:
            return []

    order_col = "title COLLATE NOCASE" if sort == "alpha" else "created_at DESC"

    if q:
        ordered_title_ids = _title_match_ids(conn, q)
        if candidate_ids is not None:
            ordered_title_ids = [rid for rid in ordered_title_ids if rid in candidate_ids]
        if not ordered_title_ids:
            return []
        if sort == "alpha":
            # Re-sort FTS results alphabetically
            placeholders = ",".join("?" * len(ordered_title_ids))
            rows = conn.execute(
                f"SELECT id FROM recipes WHERE id IN ({placeholders}) ORDER BY {order_col}",
                tuple(ordered_title_ids),
            ).fetchall()
            ordered_ids = [int(r["id"]) for r in rows]
        else:
            ordered_ids = ordered_title_ids
        page_ids = ordered_ids[offset : offset + limit]
    elif candidate_ids is not None:
        placeholders = ",".join("?" * len(candidate_ids))
        rows = conn.execute(
            f"SELECT id FROM recipes WHERE id IN ({placeholders}) ORDER BY {order_col}",
            tuple(candidate_ids),
        ).fetchall()
        ordered_ids = [int(r["id"]) for r in rows]
        page_ids = ordered_ids[offset : offset + limit]
    else:
        rows = conn.execute(
            f"SELECT id FROM recipes ORDER BY {order_col} LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        page_ids = [int(r["id"]) for r in rows]

    return [_hydrate_match(conn, rid, matched_names) for rid in page_ids]


def random_recipe(
    conn: sqlite3.Connection,
    *,
    ingredients: Optional[list[str]] = None,
    tag: Optional[str] = None,
) -> Optional[RecipeMatch]:
    candidates = search_recipes(
        conn,
        ingredients=ingredients,
        tag=tag,
        limit=10_000,
    )
    if not candidates:
        return None
    import random as _random  # local import keeps module pure for unit tests
    return _random.choice(candidates)


def _hydrate_match(
    conn: sqlite3.Connection, recipe_id: int, matched_names: list[str]
) -> RecipeMatch:
    row = conn.execute(
        """
        SELECT r.id, r.title, r.subtitle, r.image_path, r.total_time_min, r.servings,
               (SELECT COUNT(*) FROM recipe_ingredients ri WHERE ri.recipe_id = r.id) AS ic
        FROM recipes r WHERE r.id = ?
        """,
        (recipe_id,),
    ).fetchone()
    tags = [
        r["tag"]
        for r in conn.execute(
            "SELECT tag FROM tags WHERE recipe_id = ? ORDER BY tag", (recipe_id,)
        )
    ]
    ing_rows = conn.execute(
        """
        SELECT i.name FROM recipe_ingredients ri JOIN ingredients i ON i.id = ri.ingredient_id
        WHERE ri.recipe_id = ? AND ri.is_pantry = 0 ORDER BY i.name
        """,
        (recipe_id,),
    ).fetchall()
    all_names = [r["name"] for r in ing_rows]
    # An ingredient counts as "matched" if it contains any of the user's tokens
    # (substring), so "pechuga de pollo" is matched by the token "pollo".
    tokens_lower = [t.lower() for t in matched_names]
    def _is_matched(name: str) -> bool:
        nl = name.lower()
        return any(t in nl for t in tokens_lower)
    missing = [n for n in all_names if not _is_matched(n)]
    return RecipeMatch(
        id=int(row["id"]),
        title=row["title"],
        subtitle=row["subtitle"],
        image_path=row["image_path"],
        total_time_min=row["total_time_min"],
        servings=int(row["servings"]) if row["servings"] is not None else None,
        ingredient_count=int(row["ic"]),
        tags=tags,
        matched_ingredients=matched_names,
        missing_ingredients=missing,
    )
