"""FastAPI application entry point."""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import db
from .extraction.common import load_dotenv_once
from .routers import extract, ingredients, recipes, search, style_variants

app = FastAPI(title="Recetary", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Order matters: search.router has /recipes/random which would otherwise be
# captured by recipes.router's /recipes/{recipe_id} (and rejected as a
# non-integer). Same reason extract.router (/recipes/extract) goes first.
app.include_router(search.router)
app.include_router(extract.router)
app.include_router(recipes.router)
app.include_router(ingredients.router)
app.include_router(style_variants.router)

# Serve recipe images stored in data/images/
_images_dir = db.REPO_ROOT / "data" / "images"
_images_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/images", StaticFiles(directory=str(_images_dir)), name="images")

# Serve bulk style variants stored in data/style_variants/
_variants_dir = db.REPO_ROOT / "data" / "style_variants"
_variants_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/style-variants", StaticFiles(directory=str(_variants_dir)), name="style_variants")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/info")
def info() -> dict[str, str]:
    load_dotenv_once()
    backend = os.environ.get("EXTRACTOR_BACKEND", "claude").lower()
    image_backend = os.environ.get("IMAGE_BACKEND", "imagen").lower()
    return {"extractor_backend": backend, "image_backend": image_backend}
