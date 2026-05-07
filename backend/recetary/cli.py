"""Command-line interface for recetary."""
from __future__ import annotations

import argparse
import sys

from . import db


def cmd_init(_args: argparse.Namespace) -> int:
    path = db.init_db()
    print(f"Database initialized at {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="recetary")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create the database and load the schema")
    p_init.set_defaults(func=cmd_init)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
