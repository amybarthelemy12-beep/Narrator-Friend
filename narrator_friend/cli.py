"""Command-line entry point: `python -m narrator_friend book.pdf` (or .docx)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analyzer import DEFAULT_WORDS_PER_HOUR
from .costs import (
    DEFAULT_EDITING_RATE,
    DEFAULT_NARRATOR_RATE,
    DEFAULT_PROOFING_RATE,
    EXPERIENCE_RATES,
    estimate_costs,
)
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
        "--experience",
        choices=list(EXPERIENCE_RATES.keys()),
        help="ACX-scale narrator experience preset (sets --narrator-rate)",
    )
    parser.add_argument(
        "--narrator-rate",
        type=float,
        default=None,
        help=f"Narrator $/finished hour (default: {DEFAULT_NARRATOR_RATE:.0f}; overrides --experience)",
    )
    parser.add_argument(
        "--editing-rate",
        type=float,
        default=DEFAULT_EDITING_RATE,
        help="Editing & mastering $/finished hour (default: %(default)s)",
    )
    parser.add_argument(
        "--proofing-rate",
        type=float,
        default=0.0,
        help=f"Proofing $/finished hour, 0 to skip (typical: {DEFAULT_PROOFING_RATE:.0f})",
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

    if args.narrator_rate is not None:
        narrator_rate = args.narrator_rate
    elif args.experience:
        narrator_rate = EXPERIENCE_RATES[args.experience]
    else:
        narrator_rate = DEFAULT_NARRATOR_RATE

    costs = estimate_costs(
        total_words=report.totals.total_words,
        words_per_hour=report.words_per_hour,
        narrator_rate=narrator_rate,
        editing_rate=args.editing_rate,
        proofing_rate=args.proofing_rate,
    )

    if args.json:
        out = report.to_dict()
        out["cost_estimate"] = costs.to_dict()
        print(json.dumps(out, indent=2))
    else:
        print(format_text_report(report))
        print()
        print(_format_costs(costs))
    return 0


def _format_costs(c) -> str:
    lines = [
        "Production cost estimate",
        "-" * 40,
        f"  Finished hours:        {c.finished_hours:>8.2f}",
        f"  Narrator   @ ${c.narrator_rate:>6.0f}/hr: ${c.narrator_cost:>10,.0f}",
        f"  Editing    @ ${c.editing_rate:>6.0f}/hr: ${c.editing_cost:>10,.0f}",
    ]
    if c.proofing_rate > 0:
        lines.append(f"  Proofing   @ ${c.proofing_rate:>6.0f}/hr: ${c.proofing_cost:>10,.0f}")
    lines.append("-" * 40)
    lines.append(f"  TOTAL:                       ${c.total_cost:>10,.0f}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
