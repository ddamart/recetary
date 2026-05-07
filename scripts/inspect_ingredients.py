"""Look at how chicken / curry ingredients were canonicalized."""
import sys, sqlite3
from pathlib import Path
for s in (sys.stdout, sys.stderr):
    if hasattr(s, "reconfigure"):
        s.reconfigure(encoding="utf-8")

c = sqlite3.connect(Path("data/recetary.db"))
c.row_factory = sqlite3.Row

print("Ingredients matching 'pollo':")
for r in c.execute("SELECT name, category FROM ingredients WHERE name LIKE '%pollo%' ORDER BY name"):
    n = c.execute("SELECT COUNT(*) FROM recipe_ingredients WHERE ingredient_id = (SELECT id FROM ingredients WHERE name = ?)", (r["name"],)).fetchone()[0]
    print(f"  {r['name']:<35} ({r['category']})  in {n} recipe(s)")

print("\nIngredients matching 'curry':")
for r in c.execute("SELECT name, category FROM ingredients WHERE name LIKE '%curry%' ORDER BY name"):
    n = c.execute("SELECT COUNT(*) FROM recipe_ingredients WHERE ingredient_id = (SELECT id FROM ingredients WHERE name = ?)", (r["name"],)).fetchone()[0]
    print(f"  {r['name']:<35} ({r['category']})  in {n} recipe(s)")

print("\nAll 'fideos'/'noodles':")
for r in c.execute("SELECT name FROM ingredients WHERE name LIKE '%fideo%' OR name LIKE '%noodle%' OR name LIKE '%udon%' ORDER BY name"):
    n = c.execute("SELECT COUNT(*) FROM recipe_ingredients WHERE ingredient_id = (SELECT id FROM ingredients WHERE name = ?)", (r["name"],)).fetchone()[0]
    print(f"  {r['name']:<35}  in {n} recipe(s)")
