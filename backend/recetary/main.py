"""FastAPI application entry point."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import db
from .routers import extract, ingredients, recipes, search

app = FastAPI(title="Recetary", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recipes.router)
app.include_router(ingredients.router)
app.include_router(extract.router)
app.include_router(search.router)

# Serve recipe images stored in data/images/
_images_dir = db.REPO_ROOT / "data" / "images"
_images_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/images", StaticFiles(directory=str(_images_dir)), name="images")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
