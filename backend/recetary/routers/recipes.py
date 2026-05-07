"""Recipe CRUD endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from .. import db, repo
from ..models import Recipe, RecipeCreate, RecipeSummary

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("/tags", response_model=list[str])
def list_tags() -> list[str]:
    with db.get_conn() as conn:
        return repo.list_tags(conn)


@router.get("", response_model=list[RecipeSummary])
def list_recipes(
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
    tag: Optional[str] = None,
) -> list[RecipeSummary]:
    with db.get_conn() as conn:
        return repo.list_recipes(conn, limit=limit, offset=offset, tag=tag)


@router.post("", response_model=Recipe, status_code=status.HTTP_201_CREATED)
def create_recipe(payload: RecipeCreate) -> Recipe:
    with db.get_conn() as conn:
        recipe_id = repo.create_recipe(conn, payload)
        recipe = repo.get_recipe(conn, recipe_id)
    assert recipe is not None
    return recipe


@router.get("/{recipe_id}", response_model=Recipe)
def get_recipe(recipe_id: int) -> Recipe:
    with db.get_conn() as conn:
        recipe = repo.get_recipe(conn, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="recipe not found")
    return recipe


@router.put("/{recipe_id}", response_model=Recipe)
def update_recipe(recipe_id: int, payload: RecipeCreate) -> Recipe:
    with db.get_conn() as conn:
        updated = repo.update_recipe(conn, recipe_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="recipe not found")
    return updated


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipe(recipe_id: int) -> None:
    with db.get_conn() as conn:
        ok = repo.delete_recipe(conn, recipe_id)
    if not ok:
        raise HTTPException(status_code=404, detail="recipe not found")
