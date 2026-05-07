"""Search endpoints — wraps `recetary.search`."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import db
from ..models import RecipeMatch
from ..search import random_recipe, search_recipes

router = APIRouter(tags=["search"])


def _split_ingredients(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [p.strip() for p in value.split(",") if p.strip()]


@router.get("/search", response_model=list[RecipeMatch])
def search(
    q: Optional[str] = Query(None, description="Free-text title search"),
    ingredients: Optional[str] = Query(
        None, description="Comma-separated ingredient list"
    ),
    tag: Optional[str] = Query(None),
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[RecipeMatch]:
    with db.get_conn() as conn:
        return search_recipes(
            conn,
            q=q,
            ingredients=_split_ingredients(ingredients),
            tag=tag,
            limit=limit,
            offset=offset,
        )


@router.get("/recipes/random", response_model=RecipeMatch)
def random_(
    ingredients: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
) -> RecipeMatch:
    with db.get_conn() as conn:
        match = random_recipe(
            conn, ingredients=_split_ingredients(ingredients), tag=tag
        )
    if match is None:
        raise HTTPException(status_code=404, detail="no recipes match")
    return match
