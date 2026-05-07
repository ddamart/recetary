"""One-shot migration: strip the legacy 'images/' prefix from recipes.image_path."""
import sqlite3
from pathlib import Path

c = sqlite3.connect(Path("data/recetary.db"))
n = c.execute("UPDATE recipes SET image_path = REPLACE(image_path, 'images/', '') WHERE image_path LIKE 'images/%'").rowcount
c.commit()
print(f"updated {n} rows")
for row in c.execute("SELECT id, image_path FROM recipes WHERE image_path IS NOT NULL ORDER BY id LIMIT 3"):
    print(f"  [{row[0]}] {row[1]}")
