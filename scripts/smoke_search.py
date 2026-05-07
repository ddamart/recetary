"""End-to-end smoke test of the search module against the imported corpus."""
import sys
for s in (sys.stdout, sys.stderr):
    if hasattr(s, "reconfigure"):
        s.reconfigure(encoding="utf-8")

from recetary import db, search

CASES = [
    ("title fuzzy: 'albondiga' (typo, no accent)", dict(q="albondiga"), None),
    ("title fuzzy: 'curry'", dict(q="curry"), None),
    ("intersection: cebolla + tomate", dict(ingredients=["cebolla", "tomate"]), None),
    ("intersection: pollo + curry", dict(ingredients=["pollo", "curry"]), None),
    ("intersection w/ typo: cebola + tomte", dict(ingredients=["cebola", "tomte"]), None),
    ("intersection: queso mozzarella", dict(ingredients=["queso mozzarella"]), None),
    ("ingredient solo: bulgur", dict(ingredients=["bulgur"]), 5),
    ("ingredient unknown: xyzzy", dict(ingredients=["xyzzy"]), None),
    ("title + ingredient: 'noodles' + pollo", dict(q="noodles", ingredients=["pollo"]), None),
]

with db.get_conn() as conn:
    print(f"DB has {conn.execute('SELECT COUNT(*) FROM recipes').fetchone()[0]} recipes\n")
    for label, kwargs, max_show in CASES:
        results = search.search_recipes(conn, **kwargs, limit=max_show or 24)
        print(f"=== {label}  -> {len(results)} match(es)")
        for r in results[: max_show or 3]:
            extras = ""
            if r.matched_ingredients:
                extras = f"  matched={r.matched_ingredients}"
            print(f"   [{r.id:>2}]  {r.title}{extras}")
            if r.missing_ingredients and r.matched_ingredients:
                shown = r.missing_ingredients[:5]
                more = "" if len(r.missing_ingredients) <= 5 else f", +{len(r.missing_ingredients)-5}"
                print(f"        también necesitas: {', '.join(shown)}{more}")
        print()

    print("=== random recipe with pollo ===")
    rand = search.random_recipe(conn, ingredients=["pollo"])
    if rand:
        print(f"   [{rand.id}] {rand.title}")
