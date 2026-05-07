"""Command-line interface for recetary."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import db, repo
from .models import RecipeCreate

# Windows consoles default to cp1252; force UTF-8 so Spanish text renders.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")


def cmd_init(_args: argparse.Namespace) -> int:
    path = db.init_db()
    print(f"Database initialized at {path}")
    return 0


def cmd_add_text(args: argparse.Namespace) -> int:
    """Add a recipe from a structured JSON file (or stdin if path is '-')."""
    if args.text == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(args.text).read_text(encoding="utf-8")
    payload = RecipeCreate.model_validate_json(raw)
    with db.get_conn() as conn:
        recipe_id = repo.create_recipe(conn, payload)
    print(f"Created recipe id={recipe_id}: {payload.title}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    with db.get_conn() as conn:
        recipes = repo.list_recipes(conn, limit=args.limit, offset=0)
    for r in recipes:
        time = f"{r.total_time_min}m" if r.total_time_min else "  -"
        print(f"  [{r.id:>4}]  {time}  {r.title}")
    print(f"-- {len(recipes)} recipes")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="recetary")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create the database and load the schema")
    p_init.set_defaults(func=cmd_init)

    p_add = sub.add_parser("add", help="Add a recipe")
    p_add.add_argument(
        "--text",
        metavar="JSON_PATH",
        help="Path to a JSON file matching RecipeCreate (or - for stdin)",
    )
    p_add.set_defaults(func=cmd_add_text)

    p_list = sub.add_parser("list", help="List stored recipes")
    p_list.add_argument("--limit", type=int, default=50)
    p_list.set_defaults(func=cmd_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "add" and not args.text:
        parser.error("`add` currently requires --text JSON_PATH (Phase 3 will add --pdf/--image/--url)")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
