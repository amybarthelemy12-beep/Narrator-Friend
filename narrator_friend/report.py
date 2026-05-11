"""Build a per-chapter report from parsed Chapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import List, Optional

from .analyzer import (
    DEFAULT_WORDS_PER_HOUR,
    Breakdown,
    analyze_chapter,
    recording_time,
)
from .costs import finished_hours as _finished_hours
from .parser import Chapter


@dataclass
class ChapterReport:
    index: int
    title: str
    pov: Optional[str]
    page_start: Optional[int]
    breakdown: Breakdown
    recording_time: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["breakdown"] = {
            **asdict(self.breakdown),
            "dialogue_pct": round(self.breakdown.dialogue_pct, 1),
            "narration_pct": round(self.breakdown.narration_pct, 1),
            "tag_pct": round(self.breakdown.tag_pct, 1),
        }
        return d


@dataclass
class Report:
    chapters: List[ChapterReport]
    totals: Breakdown
    total_recording_time: str
    total_finished_hours: float
    words_per_hour: int

    def to_dict(self) -> dict:
        return {
            "words_per_hour": self.words_per_hour,
            "total_recording_time": self.total_recording_time,
            "total_finished_hours": round(self.total_finished_hours, 3),
            "totals": {
                **asdict(self.totals),
                "dialogue_pct": round(self.totals.dialogue_pct, 1),
                "narration_pct": round(self.totals.narration_pct, 1),
                "tag_pct": round(self.totals.tag_pct, 1),
            },
            "chapters": [c.to_dict() for c in self.chapters],
        }


def build_report(
    chapters: List[Chapter], words_per_hour: int = DEFAULT_WORDS_PER_HOUR
) -> Report:
    chapter_reports: List[ChapterReport] = []
    total = Breakdown(0, 0, 0, 0, 0)
    for i, chapter in enumerate(chapters, start=1):
        b = analyze_chapter(chapter)
        chapter_reports.append(
            ChapterReport(
                index=i,
                title=chapter.title,
                pov=chapter.pov,
                page_start=chapter.page_start,
                breakdown=b,
                recording_time=recording_time(b.total_words, words_per_hour),
            )
        )
        total = Breakdown(
            total_words=total.total_words + b.total_words,
            dialogue_words=total.dialogue_words + b.dialogue_words,
            narration_words=total.narration_words + b.narration_words,
            tag_words=total.tag_words + b.tag_words,
            dialogue_lines=total.dialogue_lines + b.dialogue_lines,
        )

    return Report(
        chapters=chapter_reports,
        totals=total,
        total_recording_time=recording_time(total.total_words, words_per_hour),
        total_finished_hours=_finished_hours(total.total_words, words_per_hour),
        words_per_hour=words_per_hour,
    )


def format_text_report(report: Report) -> str:
    lines: List[str] = []
    header = (
        f"{'#':>3}  {'Pg':>4}  {'Title':<38}  {'POV':<14}  "
        f"{'Words':>6}  {'Dial':>5}  {'Narr':>5}  {'Tags':>4}  {'Time':>6}"
    )
    lines.append(header)
    lines.append("-" * len(header))

    for c in report.chapters:
        title = (c.title or "")[:36]
        pov = (c.pov or "")[:14]
        page = c.page_start or ""
        b = c.breakdown
        lines.append(
            f"{c.index:>3}  {page!s:>4}  {title:<38}  {pov:<14}  "
            f"{b.total_words:>6}  "
            f"{b.dialogue_pct:>4.0f}%  {b.narration_pct:>4.0f}%  "
            f"{b.tag_pct:>3.0f}%  {c.recording_time:>6}"
        )

    lines.append("-" * len(header))
    t = report.totals
    lines.append(
        f"{'TOTAL':>3}  {'':>4}  {'':<38}  {'':<14}  "
        f"{t.total_words:>6}  "
        f"{t.dialogue_pct:>4.0f}%  {t.narration_pct:>4.0f}%  "
        f"{t.tag_pct:>3.0f}%  {report.total_recording_time:>6}"
    )
    lines.append("")
    lines.append(
        f"Estimated at {report.words_per_hour:,} finished words / hour. "
        f"{t.dialogue_lines} lines of dialogue across {len(report.chapters)} chapter(s)."
    )
    return "\n".join(lines)
