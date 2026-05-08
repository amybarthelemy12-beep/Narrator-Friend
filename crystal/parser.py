"""PDF parsing: extract text and split into chapters."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import pypdf


@dataclass
class Chapter:
    title: str
    text: str
    page_start: Optional[int] = None
    pov: Optional[str] = None


_NUMBER_WORDS = (
    "one|two|three|four|five|six|seven|eight|nine|ten|"
    "eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
    "nineteen|twenty|thirty|forty|fifty"
)
_CHAPTER_HEADING = re.compile(
    r"^\s*("
    r"prologue|epilogue|interlude|"
    r"part\s+(?:[ivxlc\d]+|" + _NUMBER_WORDS + r")|"
    r"chapter\s+(?:[ivxlc\d]+|" + _NUMBER_WORDS + r"(?:[\s-](?:" + _NUMBER_WORDS + r"))?)"
    r")\b[^\n]{0,80}$",
    re.IGNORECASE,
)


def parse_pdf(pdf_path: str) -> List[Chapter]:
    """Parse a PDF into a list of Chapters using bookmarks first, then heuristic."""
    reader = pypdf.PdfReader(pdf_path)
    pages = [(page.extract_text() or "") for page in reader.pages]

    outline = _outline_chapters(reader)
    if outline:
        chapters = _split_by_outline(pages, outline)
        if len(chapters) >= 2:
            return _post_process(chapters)

    return _post_process(_split_heuristic(pages))


def _outline_chapters(reader: pypdf.PdfReader) -> List[Tuple[str, int]]:
    chapters: List[Tuple[str, int]] = []

    def walk(items):
        for item in items:
            if isinstance(item, list):
                walk(item)
                continue
            try:
                page_idx = reader.get_destination_page_number(item)
                title = (getattr(item, "title", None) or "").strip()
            except Exception:
                continue
            if title:
                chapters.append((title, page_idx))

    try:
        walk(reader.outline)
    except Exception:
        return []

    chapters.sort(key=lambda c: c[1])
    # Filter outline entries that look like front-matter / non-chapters only if we
    # have enough chapter-shaped entries to stand on their own.
    chapter_like = [
        c for c in chapters
        if _CHAPTER_HEADING.match(c[0]) or re.match(r"^\s*\d+\b", c[0])
    ]
    if len(chapter_like) >= 2:
        return chapter_like
    return chapters


def _split_by_outline(
    pages: Sequence[str], outline: Sequence[Tuple[str, int]]
) -> List[Chapter]:
    chapters: List[Chapter] = []
    for i, (title, page_idx) in enumerate(outline):
        end = outline[i + 1][1] if i + 1 < len(outline) else len(pages)
        text = "\n".join(pages[page_idx:end])
        chapters.append(Chapter(title=title, text=text, page_start=page_idx + 1))
    return chapters


def _split_heuristic(pages: Sequence[str]) -> List[Chapter]:
    # Track which page each line came from so we can record page_start.
    lines: List[Tuple[str, int]] = []
    for page_idx, page_text in enumerate(pages):
        for raw_line in page_text.split("\n"):
            lines.append((raw_line, page_idx + 1))

    starts: List[int] = []
    for i, (line, _) in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if _CHAPTER_HEADING.match(stripped):
            starts.append(i)

    if not starts:
        return [Chapter(title="Manuscript", text="\n".join(l for l, _ in lines), page_start=1)]

    chapters: List[Chapter] = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        title = lines[start][0].strip()
        body = "\n".join(l for l, _ in lines[start + 1:end])
        chapters.append(Chapter(title=title, text=body, page_start=lines[start][1]))
    return chapters


def _post_process(chapters: List[Chapter]) -> List[Chapter]:
    cleaned: List[Chapter] = []
    for ch in chapters:
        text = _strip_running_headers(ch.text)
        ch.text = text
        ch.pov = detect_pov(ch.title, text)
        cleaned.append(ch)
    return cleaned


def _strip_running_headers(text: str) -> str:
    """Drop bare page-number lines (very common artifact of PDF extraction)."""
    out = []
    for line in text.split("\n"):
        if re.match(r"^\s*\d{1,4}\s*$", line):
            continue
        out.append(line)
    return "\n".join(out)


_POV_SUFFIX = re.compile(r"['’]s\s+POV\s*$", re.IGNORECASE)


def detect_pov(title: str, text: str) -> Optional[str]:
    """Detect a POV character. Looks at the chapter title first, then the
    first few non-empty lines of body text.
    """
    candidate = _pov_from_title(title)
    if candidate:
        return candidate

    for line in _first_nonempty_lines(text, limit=4):
        cand = _name_like(line)
        if cand:
            return cand
    return None


def _pov_from_title(title: str) -> Optional[str]:
    if not title:
        return None
    # "Chapter 3 — Sarah" / "Chapter 3: Sarah" / "Chapter 3 - Sarah's POV"
    m = re.search(r"[-:—–]\s*(.+?)\s*$", title)
    if m:
        cand = _name_like(m.group(1))
        if cand:
            return cand
    # Title that's literally just a name (no Chapter prefix at all).
    if not re.match(r"^\s*(chapter|part|prologue|epilogue|interlude)\b", title, re.I):
        cand = _name_like(title)
        if cand:
            return cand
    return None


def _first_nonempty_lines(text: str, limit: int) -> List[str]:
    out = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            continue
        out.append(s)
        if len(out) >= limit:
            break
    return out


def _name_like(s: str) -> Optional[str]:
    """Return a tidy name if `s` looks like a POV header, else None."""
    s = s.strip().strip(".,:;")
    if not s:
        return None

    s = _POV_SUFFIX.sub("", s).strip()
    if not s:
        return None

    if len(s) > 40:
        return None

    parts = re.split(r"\s*(?:&|/| and )\s*", s)
    if not 1 <= len(parts) <= 3:
        return None

    cleaned_parts = []
    for p in parts:
        p = p.strip()
        if not p:
            return None
        # Each part: 1-2 word capitalised name (e.g. "Sarah", "Mary Anne", "SARAH")
        words = p.split()
        if not 1 <= len(words) <= 2:
            return None
        for w in words:
            if not re.match(r"^[A-Z][a-zA-Z'\-]+$|^[A-Z]{2,}$", w):
                return None
        cleaned_parts.append(" ".join(w.title() if w.isupper() else w for w in words))

    return " & ".join(cleaned_parts)
