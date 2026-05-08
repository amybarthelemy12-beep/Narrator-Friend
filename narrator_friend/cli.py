"""Command-line entry point: `python -m narrator_friend book.pdf` (or .docx)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analyzer import DEFAULT_WORDS_PER_HOUR
from .parser import parse_manuscript
from .report import build_report, format_text_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="narrator-friend",
        description="Per-chapter manuscript breakdown for narrators.",
    )
    parser.add_argument("manuscript", help="Path to manuscript PDF or .docx")
    parser.add_argument(
        "--wph",
        type=int,
        default=DEFAULT_WORDS_PER_HOUR,
        help="Finished words per hour (default: %(default)s)",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit JSON instead of a text table"
    )
    args = parser.parse_args(argv)

    src = Path(args.manuscript)
    if not src.is_file():
        print(f"narrator-friend: file not found: {src}", file=sys.stderr)
        return 2

    try:
        chapters = parse_manuscript(str(src))
    except ValueError as exc:
        print(f"narrator-friend: {exc}", file=sys.stderr)
        return 2
    report = build_report(chapters, words_per_hour=args.wph)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(format_text_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
