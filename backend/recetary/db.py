"""SQLite connection helpers and schema bootstrap."""
from __future__ import annotations

import os
import sqlite3
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .extraction.video import source_identity

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "recetary.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _strip_diacritics(s: str | None) -> str:
    """Remove combining marks so 'asiática' → 'asiatica'."""
    if not s:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def db_path() -> Path:
    override = os.environ.get("RECETARY_DB")
    return Path(override) if override else DEFAULT_DB_PATH


def connect(path: Path | None = None) -> sqlite3.Connection:
    target = path or db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.create_function("strip_diacritics", 1, _strip_diacritics)
    return conn


@contextmanager
def get_conn(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path: Path | None = None) -> Path:
    target = path or db_path()
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_conn(target) as conn:
        conn.executescript(schema)
        _sync_recipe_sources(conn)
    return target


def _sync_recipe_sources(conn: sqlite3.Connection) -> None:
    """Register existing one-recipe sources without deleting legacy rows."""
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'recipes'"
    ).fetchone():
        return
    rows = conn.execute(
        "SELECT id, source_ref FROM recipes "
        "WHERE source_ref IS NOT NULL ORDER BY created_at, id"
    ).fetchall()
    for row in rows:
        identity = source_identity(row["source_ref"])
        if not identity or identity[0] == "youtube":
            continue
        conn.execute(
            "INSERT OR IGNORE INTO recipe_sources(source_platform, source_id, recipe_id) "
            "VALUES (?, ?, ?)",
            (*identity, row["id"]),
        )
