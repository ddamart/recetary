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


def test_duplicate_source_returns_conflict(temp_db):
    client = _client()
    payload = {
        "title": "Primera",
        "source_type": "video",
        "source_ref": "https://www.instagram.com/reel/DdYem-CstWf/",
        "steps": [{"text": "paso"}],
    }
    first = client.post("/recipes", json=payload)
    assert first.status_code == 201
    check = client.get("/recipes/source-check", params={"url": payload["source_ref"]})
    assert check.status_code == 200
    assert check.json()["duplicate"] is True
    assert check.json()["title"] == "Primera"

    duplicate = dict(payload, title="Duplicada")
    duplicate["source_ref"] = (
        "https://www.instagram.com/inigoisaosakai/reel/DdYem-CstWf/"
    )
    response = client.post("/recipes", json=duplicate)
    assert response.status_code == 409
    assert "Primera" in response.json()["detail"]["message"]


def test_source_check_happens_without_extraction(temp_db):
    client = _client()
    response = client.get(
        "/recipes/source-check",
        params={"url": "https://www.instagram.com/reel/not-yet-imported/"},
    )
    assert response.status_code == 200
    assert response.json() == {"duplicate": False}
