"""Smoke tests for the FastAPI endpoints using TestClient."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"


def _client():
    from recetary.main import app  # noqa: PLC0415  — lazy so RECETARY_DB takes effect
    return TestClient(app)


def test_healthz(temp_db):
    client = _client()
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_recipe_crud_flow(temp_db):
    client = _client()
    payload = json.loads((FIXTURES / "polpette.json").read_text(encoding="utf-8"))

    response = client.post("/recipes", json=payload)
    assert response.status_code == 201, response.text
    created = response.json()
    rid = created["id"]
    assert created["title"].startswith("¡Polpette!")

    response = client.get(f"/recipes/{rid}")
    assert response.status_code == 200
    assert response.json()["servings"] == 2

    response = client.get("/recipes")
    assert response.status_code == 200
    summaries = response.json()
    assert len(summaries) == 1
    assert summaries[0]["ingredient_count"] == 9

    response = client.get("/ingredients", params={"q": "ajo"})
    assert response.status_code == 200
    names = [i["name"] for i in response.json()]
    assert "ajo" in names

    response = client.delete(f"/recipes/{rid}")
    assert response.status_code == 204
    assert client.get(f"/recipes/{rid}").status_code == 404
