"""Shared pytest fixtures."""
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture()
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point the application at a fresh database for the duration of the test."""
    db_file = tmp_path / "recetary.db"
    monkeypatch.setenv("RECETARY_DB", str(db_file))
    from recetary import db as db_module  # noqa: PLC0415
    db_module.init_db(db_file)
    yield db_file
