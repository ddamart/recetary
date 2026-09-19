"""Recipe CRUD endpoints."""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response

from .. import db, repo
from ..extraction.imagen import (
    ImageGenerationError,
    RateLimitError,
    generate_recipe_image,
    get_available_styles,
)
from ..models import Recipe, RecipeCreate, RecipeSummary

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("/count", response_model=int)
def count_recipes() -> int:
    with db.get_conn() as conn:
        return repo.count_recipes(conn)


@router.get("/tags", response_model=list[str])
def list_tags() -> list[str]:
    with db.get_conn() as conn:
        return repo.list_tags(conn)


@router.get("", response_model=list[RecipeSummary])
def list_recipes(
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
    tag: Optional[str] = None,
    sort: Optional[str] = Query(None, description="Sort order: 'recent' (default) or 'alpha'"),
) -> list[RecipeSummary]:
    with db.get_conn() as conn:
        return repo.list_recipes(conn, limit=limit, offset=offset, tag=tag, sort=sort or "recent")


@router.post("", response_model=Recipe, status_code=status.HTTP_201_CREATED)
def create_recipe(payload: RecipeCreate) -> Recipe:
    with db.get_conn() as conn:
        try:
            recipe_id = repo.create_recipe(conn, payload)
        except repo.DuplicateSourceError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": f"Esta fuente ya está guardada como «{exc.title}».",
                    "recipe_id": exc.recipe_id,
                },
            ) from exc
        recipe = repo.get_recipe(conn, recipe_id)
    assert recipe is not None
    return recipe


@router.get("/image-styles")
def list_image_styles() -> list[dict[str, str]]:
    """Return available image generation styles."""
    return get_available_styles()


@router.post("/generate-image")
async def generate_image(
    title: str = Form(...),
    subtitle: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    style: Optional[str] = Form(None),
    reference_image: Optional[UploadFile] = File(None),
) -> Response:
    """Generate a styled preview image from a recipe title."""
    ref_bytes: bytes | None = None
    ref_mime: str | None = None
    if reference_image and reference_image.size:
        ref_bytes = await reference_image.read()
        ref_mime = reference_image.content_type or "image/jpeg"
    try:
        png_bytes = await asyncio.to_thread(
            generate_recipe_image,
            title, subtitle, description, style or "ghibli",
            ref_bytes, ref_mime,
        )
    except RateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail=str(e),
            headers={"Retry-After": str(e.retry_after)} if e.retry_after else None,
        )
    except ImageGenerationError as e:
        code = 503 if "unavailable" in str(e).lower() else 502
        raise HTTPException(status_code=code, detail=str(e))
    return Response(content=png_bytes, media_type="image/png")


@router.post("/{recipe_id}/image")
async def upload_recipe_image(
    recipe_id: str,
    file: UploadFile = File(...),
) -> dict[str, str]:
    """Upload/replace the cover image for a recipe."""
    with db.get_conn() as conn:
        recipe = repo.get_recipe(conn, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="recipe not found")

    image_bytes = await file.read()
    images_dir = db.REPO_ROOT / "data" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{recipe_id}.png"
    (images_dir / filename).write_bytes(image_bytes)

    with db.get_conn() as conn:
        conn.execute(
            "UPDATE recipes SET image_path = ? WHERE id = ?", (filename, recipe_id)
        )
    return {"image_path": filename}


@router.get("/{recipe_id}", response_model=Recipe)
def get_recipe(recipe_id: str) -> Recipe:
    with db.get_conn() as conn:
        recipe = repo.get_recipe(conn, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="recipe not found")
    return recipe


@router.put("/{recipe_id}", response_model=Recipe)
def update_recipe(recipe_id: str, payload: RecipeCreate) -> Recipe:
    with db.get_conn() as conn:
        try:
            updated = repo.update_recipe(conn, recipe_id, payload)
        except repo.DuplicateSourceError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": f"Esta fuente ya está guardada como «{exc.title}».",
                    "recipe_id": exc.recipe_id,
                },
            ) from exc
    if not updated:
        raise HTTPException(status_code=404, detail="recipe not found")
    return updated


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipe(recipe_id: str) -> None:
    with db.get_conn() as conn:
        ok = repo.delete_recipe(conn, recipe_id)
    if not ok:
        raise HTTPException(status_code=404, detail="recipe not found")
