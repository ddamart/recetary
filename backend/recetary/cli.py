"""Command-line interface for recetary."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from . import db, repo
from .extraction import (
    ExtractionError,
    RecipeDraft,
    draft_to_create,
    get_extractor,
)
from .extraction import images as image_io
from .extraction import pdf as pdf_io
from .extraction import url as url_io
from .extraction import video as video_io
from .extraction.video import VideoExtractionError
from .models import RecipeCreate, SourceType

# Windows consoles default to cp1252; force UTF-8 so Spanish text renders.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _canonical_ingredient_names() -> list[str]:
    with db.get_conn() as conn:
        rows = conn.execute("SELECT name FROM ingredients ORDER BY name").fetchall()
    return [r["name"] for r in rows]


def _save_cover_image(recipe_id: int, image_bytes: bytes, ext: str = "png") -> str:
    """Save a recipe's cover image under data/images/ and return the filename
    (relative to the /static/images mount the API exposes)."""
    images_dir = db.REPO_ROOT / "data" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{recipe_id}.{ext}"
    (images_dir / filename).write_bytes(image_bytes)
    return filename


def _commit_recipe(payload: RecipeCreate, *, cover_png: Optional[bytes] = None) -> int:
    with db.get_conn() as conn:
        recipe_id = repo.create_recipe(conn, payload)
    if cover_png:
        relative = _save_cover_image(recipe_id, cover_png, ext="png")
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE recipes SET image_path = ? WHERE id = ?", (relative, recipe_id)
            )
    return recipe_id


def _print_summary(recipe_id: int, draft: RecipeDraft) -> None:
    print(f"  ✓ id={recipe_id}  {draft.title}")
    print(
        f"    {len(draft.ingredients)} ingredientes, "
        f"{len(draft.steps)} pasos, "
        f"{draft.total_time_min or '-'} min"
    )


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def cmd_init(_args: argparse.Namespace) -> int:
    path = db.init_db()
    print(f"Database initialized at {path}")
    return 0


def cmd_add_json(args: argparse.Namespace) -> int:
    """Add a recipe from a structured JSON file (or stdin if path is '-')."""
    raw = sys.stdin.read() if args.json == "-" else Path(args.json).read_text(encoding="utf-8")
    payload = RecipeCreate.model_validate_json(raw)
    recipe_id = _commit_recipe(payload)
    print(f"Created recipe id={recipe_id}: {payload.title}")
    return 0


def _run_pdf(extractor, pdf_path: Path) -> tuple[int, RecipeDraft]:
    pdf_bytes = pdf_io.read_bytes(pdf_path)
    draft = extractor.extract(
        canonical_ingredients=_canonical_ingredient_names(),
        pdf_bytes=pdf_bytes,
        source_hint=pdf_path.name,
    )
    payload = draft_to_create(
        draft,
        source_type="pdf",
        source_ref=str(pdf_path.resolve()),
    )
    cover_png = pdf_io.render_cover_png(pdf_bytes)
    recipe_id = _commit_recipe(payload, cover_png=cover_png)
    return recipe_id, draft


def cmd_add(args: argparse.Namespace) -> int:
    extractor = get_extractor()

    if args.pdf:
        path = Path(args.pdf)
        recipe_id, draft = _run_pdf(extractor, path)
        _print_summary(recipe_id, draft)
        return 0

    if args.image:
        path = Path(args.image)
        media_type = image_io.detect_media_type(path)
        image_bytes = image_io.read_bytes(path)
        draft = extractor.extract(
            canonical_ingredients=_canonical_ingredient_names(),
            image_bytes=image_bytes,
            image_media_type=media_type,
            source_hint=path.name,
        )
        payload = draft_to_create(
            draft,
            source_type="image",
            source_ref=str(path.resolve()),
            image_path=None,
        )
        recipe_id = _commit_recipe(payload, cover_png=image_bytes if media_type == "image/png" else None)
        _print_summary(recipe_id, draft)
        return 0

    if args.text:
        text = sys.stdin.read() if args.text == "-" else Path(args.text).read_text(encoding="utf-8")
        draft = extractor.extract(
            canonical_ingredients=_canonical_ingredient_names(),
            text=text,
        )
        payload = draft_to_create(
            draft,
            source_type="text",
            raw_text=text,
        )
        recipe_id = _commit_recipe(payload)
        _print_summary(recipe_id, draft)
        return 0

    if args.url:
        cleaned = url_io.fetch_clean_text(args.url)
        if not cleaned:
            print(f"Could not extract readable content from {args.url}", file=sys.stderr)
            return 2
        draft = extractor.extract(
            canonical_ingredients=_canonical_ingredient_names(),
            text=cleaned,
            source_hint=args.url,
        )
        payload = draft_to_create(
            draft,
            source_type="url",
            source_ref=args.url,
            raw_text=cleaned,
        )
        recipe_id = _commit_recipe(payload)
        _print_summary(recipe_id, draft)
        return 0

    if args.video:
        try:
            content = video_io.fetch_video_content(args.video)
        except VideoExtractionError as e:
            print(f"Video extraction failed: {e}", file=sys.stderr)
            return 2
        draft = extractor.extract(
            canonical_ingredients=_canonical_ingredient_names(),
            text=content.text,
            image_bytes=content.thumbnail_bytes,
            image_media_type=content.thumbnail_media_type,
            source_hint=content.source_url,
        )
        payload = draft_to_create(
            draft,
            source_type="video",
            source_ref=content.source_url,
            raw_text=content.text,
        )
        cover = content.thumbnail_bytes if content.thumbnail_bytes else None
        recipe_id = _commit_recipe(payload, cover_png=cover)
        _print_summary(recipe_id, draft)
        return 0

    print("add requires one of --pdf | --image | --text | --url | --video", file=sys.stderr)
    return 2


def cmd_import_pdfs(args: argparse.Namespace) -> int:
    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"not a directory: {folder}", file=sys.stderr)
        return 2

    pdfs = sorted(folder.glob("*.pdf"))
    if args.limit:
        pdfs = pdfs[: args.limit]
    if not pdfs:
        print(f"No PDFs found in {folder}")
        return 0

    extractor = get_extractor()
    print(f"Importing {len(pdfs)} PDF(s) from {folder}\n")

    succeeded = 0
    failed = 0
    skipped = 0

    for index, pdf_path in enumerate(pdfs, start=1):
        print(f"[{index:>3}/{len(pdfs)}]  {pdf_path.name}")
        # skip if already imported (same source_ref)
        existing = _find_by_source(str(pdf_path.resolve()))
        if existing is not None and not args.force:
            print(f"    · already imported as id={existing}, skipping")
            skipped += 1
            continue
        try:
            recipe_id, draft = _run_pdf(extractor, pdf_path)
        except ExtractionError as e:
            print(f"    ✗ extraction failed: {e}")
            failed += 1
            continue
        except Exception as e:  # noqa: BLE001 — surface anything else but keep going
            print(f"    ✗ unexpected error: {e!r}")
            failed += 1
            continue
        _print_summary(recipe_id, draft)

        succeeded += 1

    print(f"\nDone — {succeeded} created, {skipped} skipped, {failed} failed")
    return 0 if failed == 0 else 1


def _find_by_source(source_ref: str) -> Optional[int]:
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM recipes WHERE source_ref = ? LIMIT 1", (source_ref,)
        ).fetchone()
    return int(row["id"]) if row else None


def cmd_list(args: argparse.Namespace) -> int:
    with db.get_conn() as conn:
        recipes = repo.list_recipes(conn, limit=args.limit, offset=0)
    for r in recipes:
        time = f"{r.total_time_min}m" if r.total_time_min else "  -"
        print(f"  [{r.id:>4}]  {time}  {r.title}")
    print(f"-- {len(recipes)} recipes")
    return 0


# ---------------------------------------------------------------------------
# argparse plumbing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="recetary")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create the database and load the schema")
    p_init.set_defaults(func=cmd_init)

    p_add_json = sub.add_parser(
        "add-json",
        help="Add a recipe from a structured JSON file (no AI)",
    )
    p_add_json.add_argument("json", help="Path to a JSON file matching RecipeCreate (or - for stdin)")
    p_add_json.set_defaults(func=cmd_add_json)

    p_add = sub.add_parser("add", help="Extract a recipe from PDF / image / text / URL via Claude")
    group = p_add.add_mutually_exclusive_group()
    group.add_argument("--pdf", metavar="PATH")
    group.add_argument("--image", metavar="PATH")
    group.add_argument("--text", metavar="PATH_OR_DASH")
    group.add_argument("--url", metavar="URL")
    group.add_argument("--video", metavar="URL", help="YouTube or Instagram video URL")
    p_add.set_defaults(func=cmd_add)

    p_import = sub.add_parser("import-pdfs", help="Bulk-extract every PDF in a folder")
    p_import.add_argument("folder")
    p_import.add_argument("--limit", type=int, help="Process at most N files")
    p_import.add_argument(
        "--force", action="store_true", help="Re-import PDFs already in the DB"
    )
    p_import.set_defaults(func=cmd_import_pdfs)

    p_list = sub.add_parser("list", help="List stored recipes")
    p_list.add_argument("--limit", type=int, default=50)
    p_list.set_defaults(func=cmd_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
