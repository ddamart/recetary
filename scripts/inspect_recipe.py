"""Pretty-print one recipe row with its children for human inspection."""
import json
import sqlite3
import sys
from pathlib import Path

recipe_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
conn = sqlite3.connect(Path("data/recetary.db"))
conn.row_factory = sqlite3.Row

recipe = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
if not recipe:
    print(f"no recipe id={recipe_id}")
    sys.exit(1)

print("=" * 78)
print(f"  {recipe['title']}")
if recipe["subtitle"]:
    print(f"  {recipe['subtitle']}")
print("=" * 78)
print(f"  servings={recipe['servings']}  total={recipe['total_time_min']}m  "
      f"cook={recipe['cook_time_min']}m  difficulty={recipe['difficulty']}  "
      f"image={recipe['image_path']}")
print(f"  source: {recipe['source_type']} {recipe['source_ref']}")
if recipe["description"]:
    print(f"\n  {recipe['description']}")

print("\nIngredientes:")
ings = conn.execute(
    """SELECT i.name, i.category, ri.quantity_raw, ri.quantity_value, ri.quantity_unit,
              ri.is_pantry, ri.notes
       FROM recipe_ingredients ri JOIN ingredients i ON i.id = ri.ingredient_id
       WHERE ri.recipe_id = ? ORDER BY ri.is_pantry, i.name""",
    (recipe_id,),
).fetchall()
for i in ings:
    pantry = " (despensa)" if i["is_pantry"] else ""
    qty = i["quantity_raw"] or "-"
    parsed = ""
    if i["quantity_value"] is not None:
        parsed = f"  [{i['quantity_value']} {i['quantity_unit']}]"
    note = f"  · {i['notes']}" if i["notes"] else ""
    print(f"  - {i['name']:<30}  {i['category']:<10}  {qty}{parsed}{note}{pantry}")

print("\nPasos:")
for s in conn.execute(
    "SELECT step_number, title, text FROM steps WHERE recipe_id = ? ORDER BY step_number",
    (recipe_id,),
):
    head = f"{s['step_number']}. {s['title']}" if s["title"] else f"{s['step_number']}."
    print(f"  {head}")
    print(f"     {s['text']}")

utensils = [r["name"] for r in conn.execute(
    "SELECT name FROM utensils WHERE recipe_id = ? ORDER BY name", (recipe_id,)
)]
print(f"\nUtensilios: {', '.join(utensils)}")

tags = [r["tag"] for r in conn.execute(
    "SELECT tag FROM tags WHERE recipe_id = ? ORDER BY tag", (recipe_id,)
)]
print(f"Tags: {', '.join(tags)}")
