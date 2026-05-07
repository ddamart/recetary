"""Ingredient listing / autocomplete endpoint."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from .. import db, repo
from ..models import IngredientOut

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


@router.get("", response_model=list[IngredientOut])
def list_ingredients(
    q: Optional[str] = Query(None, description="Substring match on name"),
    limit: int = Query(50, ge=1, le=200),
) -> list[IngredientOut]:
    with db.get_conn() as conn:
        return repo.list_ingredients(conn, query=q, limit=limit)
