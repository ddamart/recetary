"""Quick DB inspection helper for ad-hoc verification."""
import sqlite3
from pathlib import Path

c = sqlite3.connect(Path("data/recetary.db"))
rows = c.execute(
    "SELECT name, type FROM sqlite_master "
    "WHERE type IN ('table', 'index', 'trigger') "
    "ORDER BY type, name"
).fetchall()
for name, kind in rows:
    print(f"{kind:8} {name}")
