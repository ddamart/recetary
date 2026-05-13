"""Endpoints that turn raw inputs into a `RecipeDraft` via an LLM backend."""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from .. import db, repo
from ..extraction import RecipeDraft, ExtractionError, get_extractor
from ..extraction.common import VideoRecipeList
from ..extraction import images as image_io
from ..extraction import url as url_io
from ..extraction import video as video_io
from ..extraction.video import VideoExtractionError

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


@router.post("/list-video-recipes", response_model=VideoRecipeList)
async def list_video_recipes(
    url: str = Form(...),
) -> VideoRecipeList:
    """Phase 1: return a lightweight list of all recipes found in a YouTube video."""
    extractor = _get_extractor()
    if not hasattr(extractor, "list_video_recipes"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Multi-recipe listing requires the Gemini backend.",
        )

    if not video_io._extract_youtube_id(url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Multi-recipe listing is only supported for YouTube URLs.",
        )

    try:
        content = await asyncio.to_thread(video_io.fetch_video_content, url)
    except VideoExtractionError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    try:
        return await asyncio.to_thread(
            extractor.list_video_recipes,
            video_url=content.source_url,
            transcript_text=content.text,
        )
    except ExtractionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/extract", response_model=RecipeDraft)
async def extract_recipe(
    source_type: str = Form(..., description="One of: pdf, image, text, url, video"),
    text: Optional[str] = Form(None),
    url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    recipe_hint: Optional[str] = Form(None),
) -> RecipeDraft:
    extractor = _get_extractor()
    canonical = _canonical_ingredient_names()

    try:
        if source_type == "pdf":
            if file is None:
                raise HTTPException(400, "pdf source requires a file upload")
            pdf_bytes = await file.read()
            draft = await asyncio.to_thread(
                extractor.extract,
                canonical_ingredients=canonical,
                pdf_bytes=pdf_bytes,
                source_hint=file.filename,
            )
            draft.source_ref = file.filename
            return draft
        if source_type == "image":
            if file is None:
                raise HTTPException(400, "image source requires a file upload")
            image_bytes = await file.read()
            draft = await asyncio.to_thread(
                extractor.extract,
                canonical_ingredients=canonical,
                image_bytes=image_bytes,
                image_media_type=file.content_type or "image/jpeg",
                source_hint=file.filename,
            )
            draft.source_ref = file.filename
            return draft
        if source_type == "text":
            if not text or not text.strip():
                raise HTTPException(400, "text source requires the `text` field")
            return await asyncio.to_thread(
                extractor.extract,
                canonical_ingredients=canonical,
                text=text,
            )
        if source_type == "url":
            if not url:
                raise HTTPException(400, "url source requires the `url` field")
            cleaned = url_io.fetch_clean_text(url)
            if not cleaned:
                raise HTTPException(422, f"Could not extract readable content from {url}")
            draft = await asyncio.to_thread(
                extractor.extract,
                canonical_ingredients=canonical,
                text=cleaned,
                source_hint=url,
            )
            draft.source_ref = url
            return draft
        if source_type == "video":
            if not url:
                raise HTTPException(400, "video source requires the `url` field")

            # Fail fast: video bytes extraction requires Gemini (Claude cannot process raw video)
            has_video_url = (
                video_io._extract_twitter_status_id(url)
                or video_io._extract_instagram_shortcode(url)
            )
            if has_video_url and not hasattr(extractor, "extract_video_bytes"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "Video extraction from Twitter/Instagram requires the Gemini backend. "
                        "The current backend (Claude) does not support video processing."
                    ),
                )

            content = await asyncio.to_thread(video_io.fetch_video_content, url)

            # Platforms with downloaded video bytes: send to Gemini
            if content.video_bytes:
                draft = await asyncio.to_thread(
                    extractor.extract_video_bytes,
                    video_bytes=content.video_bytes,
                    video_mime_type=content.video_mime_type,
                    supplementary_text=content.text,
                    canonical_ingredients=canonical,
                )
                draft.source_ref = content.source_url
                return draft

            # Gemini can process YouTube videos natively for richer extraction
            if hasattr(extractor, "extract_video_url") and content.platform == "youtube":
                try:
                    draft = await asyncio.to_thread(
                        extractor.extract_video_url,
                        video_url=content.source_url,
                        transcript_text=content.text,
                        recipe_hint=recipe_hint,
                        canonical_ingredients=canonical,
                    )
                    draft.source_ref = content.source_url
                    return draft
                except Exception:
                    pass  # fall through to transcript-based extraction

            draft = await asyncio.to_thread(
                extractor.extract,
                canonical_ingredients=canonical,
                text=content.text,
                image_bytes=content.thumbnail_bytes,
                image_media_type=content.thumbnail_media_type,
                source_hint=content.source_url,
            )
            draft.source_ref = content.source_url
            return draft
        raise HTTPException(400, f"unknown source_type: {source_type!r}")
    except VideoExtractionError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except ExtractionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
