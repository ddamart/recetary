"""SQLite connection helpers and schema bootstrap."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "recetary.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


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
    return target
