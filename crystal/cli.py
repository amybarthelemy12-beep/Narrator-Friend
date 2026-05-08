"""Command-line entry point: `python -m crystal book.pdf`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analyzer import DEFAULT_WORDS_PER_HOUR
from .parser import parse_pdf
from .report import build_report, format_text_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crystal",
        description="Per-chapter manuscript breakdown for narrators.",
    )
    parser.add_argument("pdf", help="Path to manuscript PDF")
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

    pdf_path = Path(args.pdf)
    if not pdf_path.is_file():
        print(f"crystal: file not found: {pdf_path}", file=sys.stderr)
        return 2

    chapters = parse_pdf(str(pdf_path))
    report = build_report(chapters, words_per_hour=args.wph)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(format_text_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
