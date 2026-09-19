"""Tests for the search module: title fuzzy, ingredient intersection, random."""
from __future__ import annotations

from recetary import db, repo, search
from recetary.models import IngredientRef, RecipeCreate, StepIn


def _seed(conn, **overrides):
    base = dict(
        title="Sin título",
        servings=2,
        ingredients=[],
        steps=[StepIn(text="paso 1")],
        utensils=[],
        tags=[],
        source_type="manual",
    )
    base.update(overrides)
    return repo.create_recipe(conn, RecipeCreate(**base))


def _populate(temp_db):
    with db.get_conn() as conn:
        a = _seed(
            conn,
            title="Albóndigas italianas con tomate y mozzarella",
            ingredients=[
                IngredientRef(name="cebolla", category="vegetable", quantity_raw="1 ud"),
                IngredientRef(name="tomate", category="fruit", quantity_raw="200 g"),
                IngredientRef(name="carne picada", category="protein", quantity_raw="250 g"),
                IngredientRef(name="mozzarella", category="dairy", quantity_raw="125 g"),
            ],
            tags=["italiana"],
        )
        b = _seed(
            conn,
            title="Curry de pollo con tomate",
            ingredients=[
                IngredientRef(name="pollo", category="protein", quantity_raw="400 g"),
                IngredientRef(name="tomate", category="fruit", quantity_raw="200 g"),
                IngredientRef(name="cebolla", category="vegetable", quantity_raw="1 ud"),
                IngredientRef(name="curry", category="seasoning", quantity_raw="1 cucharadita", is_pantry=True),
            ],
            tags=["asiatica"],
        )
        c = _seed(
            conn,
            title="Ensalada césar simple",
            ingredients=[
                IngredientRef(name="lechuga", category="vegetable", quantity_raw="1 ud"),
                IngredientRef(name="pollo", category="protein", quantity_raw="200 g"),
                IngredientRef(name="parmesano", category="dairy", quantity_raw="50 g"),
            ],
            tags=[],
        )
    return a, b, c


def test_search_by_ingredient_intersection(temp_db):
    a, b, c = _populate(temp_db)
    with db.get_conn() as conn:
        results = search.search_recipes(conn, ingredients=["cebolla", "tomate"])
    ids = [r.id for r in results]
    assert set(ids) == {a, b}
    # Recipe A should also list "carne picada" and "mozzarella" as missing
    a_match = next(r for r in results if r.id == a)
    assert "carne picada" in a_match.missing_ingredients
    assert "mozzarella" in a_match.missing_ingredients
    assert sorted(a_match.matched_ingredients) == ["cebolla", "tomate"]


def test_search_ingredient_typo_resolves_via_fuzzy(temp_db):
    _populate(temp_db)
    with db.get_conn() as conn:
        results = search.search_recipes(conn, ingredients=["tomte"])  # typo
    ids = {r.id for r in results}
    # both A and B contain "tomate"
    assert len(ids) == 2


def test_search_unknown_ingredient_returns_empty(temp_db):
    _populate(temp_db)
    with db.get_conn() as conn:
        results = search.search_recipes(conn, ingredients=["xyzzy"])
    assert results == []


def test_search_title_fts_diacritic_insensitive(temp_db):
    a, _, _ = _populate(temp_db)
    with db.get_conn() as conn:
        results = search.search_recipes(conn, q="albondiga")  # missing accent
    assert any(r.id == a for r in results)


def test_search_title_plus_ingredients(temp_db):
    a, b, _ = _populate(temp_db)
    with db.get_conn() as conn:
        results = search.search_recipes(conn, q="curry", ingredients=["tomate"])
    assert [r.id for r in results] == [b]


def test_search_with_tag_filter(temp_db):
    _, b, _ = _populate(temp_db)
    with db.get_conn() as conn:
        results = search.search_recipes(conn, tag="asiatica")
    assert [r.id for r in results] == [b]


def test_random_recipe_with_filter(temp_db):
    _populate(temp_db)
    with db.get_conn() as conn:
        match = search.random_recipe(conn, ingredients=["pollo"])
    assert match is not None
    assert "pollo" in match.matched_ingredients


def test_random_recipe_returns_none_when_no_match(temp_db):
    _populate(temp_db)
    with db.get_conn() as conn:
        match = search.random_recipe(conn, ingredients=["xyzzy"])
    assert match is None


def test_token_matches_all_canonical_variants(temp_db):
    """A token like 'pollo' must match every canonical containing it
    (`pechuga de pollo`, `muslo de pollo`, ...), not just the single best."""
    with db.get_conn() as conn:
        a = _seed(
            conn,
            title="Pechuga al horno",
            ingredients=[
                IngredientRef(name="pechuga de pollo", category="protein", quantity_raw="400 g"),
                IngredientRef(name="patata", category="vegetable", quantity_raw="400 g"),
            ],
        )
        b = _seed(
            conn,
            title="Muslos a la naranja",
            ingredients=[
                IngredientRef(name="muslo de pollo deshuesado", category="protein", quantity_raw="500 g"),
                IngredientRef(name="naranja", category="fruit", quantity_raw="2 ud"),
            ],
        )
        c = _seed(
            conn,
            title="Verduras al wok",
            ingredients=[IngredientRef(name="brocoli", category="vegetable", quantity_raw="1 ud")],
        )
        results = search.search_recipes(conn, ingredients=["pollo"])
    ids = {r.id for r in results}
    assert ids == {a, b}, "token 'pollo' must match every chicken-cut variant"
    assert c not in ids


def test_resolve_ingredient_exact_and_fuzzy(temp_db):
    _populate(temp_db)
    with db.get_conn() as conn:
        exact = search.resolve_ingredient(conn, "cebolla")
        fuzzy = search.resolve_ingredient(conn, "Mozarela")  # typo + caps
    assert exact is not None and exact[1] == "cebolla" and exact[2] == 100
    assert fuzzy is not None and fuzzy[1] == "mozzarella"


def test_search_title_infix_substring(temp_db):
    """Searching 'soba' should find 'Yakisoba de verduras' via LIKE fallback."""
    with db.get_conn() as conn:
        yaki_id = _seed(conn, title="Yakisoba de verduras")
        _seed(conn, title="Ensalada de tomate")  # decoy
        results = search.search_recipes(conn, q="soba")
    assert any(r.id == yaki_id for r in results)
    assert len(results) == 1


def test_search_source_url_substring(temp_db):
    source = "https://www.youtube.com/watch?v=recipe123"
    with db.get_conn() as conn:
        recipe_id = _seed(conn, title="Pollo coreano", source_ref=source)
        results = search.search_recipes(conn, q="recipe123")
    assert [r.id for r in results] == [recipe_id]


def test_search_source_url_matches_platform_url_variants(temp_db):
    with db.get_conn() as conn:
        instagram_id = _seed(
            conn,
            title="Arroz de Instagram",
            source_ref="https://www.instagram.com/reel/DdYem-CstWf/",
        )
        youtube_id = _seed(
            conn,
            title="Pollo de YouTube",
            source_ref="https://www.youtube.com/watch?v=AbCdEfGhIjK",
        )
        twitter_id = _seed(
            conn,
            title="Pasta de X",
            source_ref="https://x.com/i/status/123456789",
        )
        instagram_results = search.search_recipes(
            conn,
            q="https://www.instagram.com/inigoisaosakai/reel/DdYem-CstWf/",
        )
        youtube_results = search.search_recipes(
            conn,
            q="https://youtu.be/AbCdEfGhIjK",
        )
        twitter_results = search.search_recipes(
            conn,
            q="https://twitter.com/cook/status/123456789",
        )

    assert [r.id for r in instagram_results] == [instagram_id]
    assert [r.id for r in youtube_results] == [youtube_id]
    assert [r.id for r in twitter_results] == [twitter_id]
