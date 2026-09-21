"""Bulk style-variant generation and selection endpoints."""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .. import db, repo
from ..extraction.imagen import STYLES, generate_recipe_image

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/style-variants", tags=["style-variants"])

VARIANTS_PER_STYLE = 5
SELECTED_VARIANTS_PER_STYLE = 10

_state: dict = {
    "running": False,
    "total": 0,
    "done": 0,
    "current": None,
    "stop_requested": False,
    "errors": 0,
}
_lock = threading.Lock()


def _variants_dir() -> Path:
    return db.REPO_ROOT / "data" / "style_variants"


def _variant_path(recipe_id: str, style: str, index: int) -> Path:
    return _variants_dir() / recipe_id / style / f"{index}.png"


def _count_existing(recipes: list, styles: list[str], variants_per_style: int) -> int:
    count = 0
    for row in recipes:
        for style in styles:
            for idx in range(variants_per_style):
                if _variant_path(row[0], style, idx).exists():
                    count += 1
    return count


def _run_generation(
    recipes: list,
    styles: list[str],
    variants_per_style: int = VARIANTS_PER_STYLE,
) -> None:
    done = _count_existing(recipes, styles, variants_per_style)
    total = len(recipes) * len(styles) * variants_per_style

    with _lock:
        _state["running"] = True
        _state["stop_requested"] = False
        _state["total"] = total
        _state["done"] = done
        _state["errors"] = 0

    for recipe_id, title, subtitle, description in recipes:
        for style in styles:
            for idx in range(variants_per_style):
                with _lock:
                    if _state["stop_requested"]:
                        _state["running"] = False
                        _state["current"] = None
                        return
                    _state["current"] = {
                        "recipe_id": recipe_id,
                        "recipe_title": title or "",
                        "style": style,
                        "index": idx + 1,
                    }

                path = _variant_path(recipe_id, style, idx)
                if path.exists():
                    continue

                try:
                    png = generate_recipe_image(
                        title=title or "",
                        subtitle=subtitle,
                        description=description,
                        style=style,
                    )
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(png)
                    logger.info("Generated variant %s/%s/%d", recipe_id, style, idx)
                    with _lock:
                        _state["done"] += 1
                except Exception as exc:
                    logger.error(
                        "Error generating variant %s/%s/%d: %s", recipe_id, style, idx, exc
                    )
                    with _lock:
                        _state["errors"] += 1

    with _lock:
        _state["running"] = False
        _state["current"] = None
    logger.info("Style variant generation complete: %d/%d done", _state["done"], total)


def _start_generation(
    recipes: list,
    styles: list[str],
    variants_per_style: int,
) -> dict:
    with _lock:
        if _state["running"]:
            return {"status": "already_running"}

    thread = threading.Thread(
        target=_run_generation,
        args=(recipes, styles, variants_per_style),
        daemon=True,
        name="style-variant-generation",
    )
    thread.start()
    return {
        "status": "started",
        "recipes": len(recipes),
        "styles": len(styles),
        "total": len(recipes) * len(styles) * variants_per_style,
    }


@router.get("/progress")
def get_progress() -> dict:
    with _lock:
        return dict(_state)


@router.post("/start")
def start_generation() -> dict:
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, subtitle, description FROM recipes ORDER BY title"
        ).fetchall()

    recipes = [(r["id"], r["title"], r["subtitle"], r["description"]) for r in rows]
    styles = ["ghibli", "ghibli-3", "watercolor", "minimal", "ghibli-new"]
    return _start_generation(recipes, styles, VARIANTS_PER_STYLE)


@router.post("/start/{recipe_id}")
def start_recipe_generation(recipe_id: str, style: str) -> dict:
    if style not in STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown style: {style}")

    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT id, title, subtitle, description FROM recipes WHERE id = ?",
            (recipe_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="recipe not found")

    recipe = [(row["id"], row["title"], row["subtitle"], row["description"])]
    return _start_generation(recipe, [style], SELECTED_VARIANTS_PER_STYLE)


@router.post("/stop")
def stop_generation() -> dict:
    with _lock:
        _state["stop_requested"] = True
    return {"status": "stop_requested"}


@router.get("/{recipe_id}")
def get_recipe_variants(recipe_id: str) -> dict:
    with db.get_conn() as conn:
        recipe = repo.get_recipe(conn, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="recipe not found")

    variants: dict[str, list[str | None]] = {}
    for style in STYLES:
        slots: list[str | None] = []
        for idx in range(SELECTED_VARIANTS_PER_STYLE):
            path = _variant_path(recipe_id, style, idx)
            slots.append(f"{recipe_id}/{style}/{idx}.png" if path.exists() else None)
        variants[style] = slots

    return {"recipe_id": recipe_id, "variants": variants}


@router.post("/{recipe_id}/{style}/{index}/select")
def select_variant(recipe_id: str, style: str, index: int) -> dict:
    if style not in STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown style: {style}")
    if not 0 <= index < VARIANTS_PER_STYLE:
        raise HTTPException(status_code=400, detail=f"Index must be 0-{VARIANTS_PER_STYLE - 1}")

    src = _variant_path(recipe_id, style, index)
    if not src.exists():
        raise HTTPException(status_code=404, detail="Variant not yet generated")

    images_dir = db.REPO_ROOT / "data" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{recipe_id}.png"
    (images_dir / filename).write_bytes(src.read_bytes())

    with db.get_conn() as conn:
        conn.execute(
            "UPDATE recipes SET image_path = ? WHERE id = ?",
            (filename, recipe_id),
        )

    return {"image_path": filename}
