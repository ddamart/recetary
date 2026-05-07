"""Endpoints that turn raw inputs into a `RecipeDraft` via an LLM backend."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from .. import db, repo
from ..extraction import RecipeDraft, ExtractionError, get_extractor
from ..extraction import images as image_io
from ..extraction import url as url_io

router = APIRouter(prefix="/recipes", tags=["extract"])

_extractor = None


def _get_extractor():
    global _extractor
    if _extractor is None:
        _extractor = get_extractor()
    return _extractor


def _canonical_ingredient_names() -> list[str]:
    with db.get_conn() as conn:
        rows = conn.execute("SELECT name FROM ingredients ORDER BY name").fetchall()
    return [r["name"] for r in rows]


@router.post("/extract", response_model=RecipeDraft)
async def extract_recipe(
    source_type: str = Form(..., description="One of: pdf, image, text, url"),
    text: Optional[str] = Form(None),
    url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
) -> RecipeDraft:
    extractor = _get_extractor()
    canonical = _canonical_ingredient_names()

    try:
        if source_type == "pdf":
            if file is None:
                raise HTTPException(400, "pdf source requires a file upload")
            pdf_bytes = await file.read()
            return extractor.extract(
                canonical_ingredients=canonical,
                pdf_bytes=pdf_bytes,
                source_hint=file.filename,
            )
        if source_type == "image":
            if file is None:
                raise HTTPException(400, "image source requires a file upload")
            image_bytes = await file.read()
            return extractor.extract(
                canonical_ingredients=canonical,
                image_bytes=image_bytes,
                image_media_type=file.content_type or "image/jpeg",
                source_hint=file.filename,
            )
        if source_type == "text":
            if not text or not text.strip():
                raise HTTPException(400, "text source requires the `text` field")
            return extractor.extract(canonical_ingredients=canonical, text=text)
        if source_type == "url":
            if not url:
                raise HTTPException(400, "url source requires the `url` field")
            cleaned = url_io.fetch_clean_text(url)
            if not cleaned:
                raise HTTPException(422, f"Could not extract readable content from {url}")
            return extractor.extract(
                canonical_ingredients=canonical,
                text=cleaned,
                source_hint=url,
            )
        raise HTTPException(400, f"unknown source_type: {source_type!r}")
    except ExtractionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
