"""Count recipes in the DB — used to monitor batch import progress."""
import sqlite3
from pathlib import Path

c = sqlite3.connect(Path("data/recetary.db"))
n = c.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
ing = c.execute("SELECT COUNT(*) FROM ingredients").fetchone()[0]
last = c.execute(
    "SELECT id, title, created_at FROM recipes ORDER BY id DESC LIMIT 3"
).fetchall()
print(f"recipes: {n}    ingredients: {ing}")
print("most recent:")
for rid, title, ts in last:
    print(f"  [{rid:>3}] {ts}  {title}")
