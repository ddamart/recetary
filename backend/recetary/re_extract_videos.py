"""Re-extract video recipes to improve quality.

Queries all recipes with source_type='video' (YouTube, Instagram, Twitter),
re-runs them through the extraction pipeline, and updates these fields:
    description, servings, total_time_min, cook_time_min, difficulty,
    ingredients, steps, utensils, tags

These fields are NOT touched:
    id, title, subtitle, image_path, source_type, source_ref, created_at

Usage:
    python -m recetary.re_extract_videos [options]

Options:
    --dry-run           Show what would be updated without writing to DB
    --recipe-id ID      Process only this one recipe
    --limit N           Stop after processing N recipes
    --delay SECONDS     Seconds to wait between recipes (default: 3)
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Optional

from . import db, repo
from .extraction import ExtractionError, draft_to_create, get_extractor
from .extraction import video as video_io
from .extraction.common import load_dotenv_once
from .extraction.video import VideoExtractionError
from .models import IngredientRef, RecipeCreate, StepIn

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")


def _canonical_ingredient_names() -> list[str]:
    with db.get_conn() as conn:
        rows = conn.execute("SELECT name FROM ingredients ORDER BY name").fetchall()
    return [r["name"] for r in rows]


def _list_video_recipes(recipe_id: Optional[str] = None) -> list[dict]:
    with db.get_conn() as conn:
        if recipe_id:
            rows = conn.execute(
                "SELECT id, title, subtitle, image_path, source_type, source_ref "
                "FROM recipes WHERE id = ? AND source_type = 'video'",
                (recipe_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, subtitle, image_path, source_type, source_ref "
                "FROM recipes WHERE source_type = 'video' ORDER BY created_at ASC"
            ).fetchall()
    return [dict(r) for r in rows]


def _re_extract_one(extractor, source_ref: str, canonical: list[str]):
    """Run extraction pipeline for a video URL. Returns RecipeDraft."""
    content = video_io.fetch_video_content(source_ref)

    if content.video_bytes:
        # Instagram / Twitter with downloaded video — needs Gemini
        if not hasattr(extractor, "extract_video_bytes"):
            raise ExtractionError(
                "Video bytes extraction requires the Gemini backend "
                "(set EXTRACTOR_BACKEND=gemini)"
            )
        draft = extractor.extract_video_bytes(
            video_bytes=content.video_bytes,
            video_mime_type=content.video_mime_type,
            supplementary_text=content.text,
            canonical_ingredients=canonical,
        )
        return draft

    # YouTube: prefer native Gemini video URL, fall back to transcript text
    if hasattr(extractor, "extract_video_url") and content.platform == "youtube":
        try:
            return extractor.extract_video_url(
                video_url=content.source_url,
                transcript_text=content.text,
                canonical_ingredients=canonical,
            )
        except Exception:
            pass  # fall through to text-based extraction

    return extractor.extract(
        canonical_ingredients=canonical,
        text=content.text,
        image_bytes=content.thumbnail_bytes,
        image_media_type=content.thumbnail_media_type,
        source_hint=content.source_url,
    )


def _apply_update(conn, recipe_id: str, original: dict, draft) -> None:
    """Update only the content fields, preserving identity and presentation fields."""
    payload = RecipeCreate(
        # Identity / presentation — kept from DB
        title=original["title"],
        subtitle=original["subtitle"],
        image_path=original["image_path"],
        source_type=original["source_type"],
        source_ref=original["source_ref"],
        # Content fields — replaced by new extraction
        description=draft.description,
        servings=max(1, min(20, draft.servings)),
        total_time_min=draft.total_time_min,
        cook_time_min=draft.cook_time_min,
        difficulty=draft.difficulty,
        ingredients=[
            IngredientRef(
                name=i.name,
                category=i.category,
                quantity_raw=i.quantity_raw,
                notes=i.notes,
                is_pantry=i.is_pantry,
            )
            for i in draft.ingredients
        ],
        steps=[StepIn(title=s.title, text=s.text) for s in draft.steps],
        utensils=list(draft.utensils),
        tags=list(draft.tags),
    )
    repo.update_recipe(conn, recipe_id, payload)


def run(
    *,
    dry_run: bool = False,
    recipe_id: Optional[str] = None,
    limit: int = 0,
    delay: float = 3.0,
) -> int:
    load_dotenv_once()
    extractor = get_extractor()

    recipes = _list_video_recipes(recipe_id)
    if not recipes:
        target = f"id={recipe_id}" if recipe_id else "source_type='video'"
        print(f"No video recipes found ({target}).")
        return 0

    if limit and limit < len(recipes):
        recipes = recipes[:limit]

    total = len(recipes)
    print(f"{'[DRY RUN] ' if dry_run else ''}Processing {total} video recipe(s)\n")

    succeeded = 0
    failed = 0
    skipped = 0

    for index, rec in enumerate(recipes, start=1):
        rid = rec["id"]
        title = rec["title"]
        source_ref = rec["source_ref"] or ""
        print(f"[{index:>3}/{total}]  {title}")
        print(f"         {source_ref}")

        if not source_ref:
            print("    · no source_ref, skipping")
            skipped += 1
            continue

        try:
            canonical = _canonical_ingredient_names()
            draft = _re_extract_one(extractor, source_ref, canonical)
        except VideoExtractionError as e:
            print(f"    x video fetch failed: {e}")
            failed += 1
        except ExtractionError as e:
            print(f"    x extraction failed: {e}")
            failed += 1
        except Exception as e:  # noqa: BLE001
            print(f"    x unexpected error: {e!r}")
            failed += 1
        else:
            print(
                f"    > {len(draft.ingredients)} ingredientes, "
                f"{len(draft.steps)} pasos, "
                f"{draft.total_time_min or '-'} min, "
                f"tags: {', '.join(draft.tags) or '-'}"
            )
            if not dry_run:
                with db.get_conn() as conn:
                    _apply_update(conn, rid, rec, draft)
                print(f"    v actualizado")
            else:
                print(f"    ~ (dry-run, no escrito)")
            succeeded += 1

        if index < total:
            time.sleep(delay)

    print(f"\nDone — {succeeded} actualizados, {skipped} saltados, {failed} fallidos")
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="re_extract_videos",
        description="Re-extract video recipes (YouTube/Instagram/Twitter) to improve quality.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without writing to the DB",
    )
    parser.add_argument(
        "--recipe-id",
        metavar="ID",
        help="Process only this recipe (must have source_type='video')",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="N",
        help="Stop after processing N recipes (0 = all)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        metavar="SECONDS",
        help="Seconds to wait between recipes (default: 3)",
    )
    args = parser.parse_args(argv)
    return run(
        dry_run=args.dry_run,
        recipe_id=args.recipe_id,
        limit=args.limit,
        delay=args.delay,
    )


if __name__ == "__main__":
    sys.exit(main())
