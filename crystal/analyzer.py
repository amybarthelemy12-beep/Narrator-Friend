"""Word-count breakdown for a chapter: dialogue, narration, tags, recording time."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

from .parser import Chapter

# ACX-style finished-hour rule of thumb. Configurable via CLI / web form.
DEFAULT_WORDS_PER_HOUR = 9300

# Common dialogue tag verbs. Action beats (e.g. "she frowned") are intentionally
# excluded — they remain narration.
TAG_VERBS = (
    "said|asked|replied|answered|whispered|shouted|yelled|murmured|muttered|"
    "growled|snapped|sighed|hissed|called|cried|exclaimed|laughed|continued|"
    "added|agreed|demanded|declared|drawled|gasped|groaned|grumbled|mumbled|"
    "noted|observed|offered|ordered|panted|pleaded|promised|protested|purred|"
    "queried|quipped|remarked|repeated|retorted|roared|scolded|screamed|"
    "snorted|sobbed|spat|stammered|stated|stuttered|suggested|teased|told|"
    "urged|vowed|warned|wondered|breathed|argued|admitted|reasoned|insisted|"
    "exhaled|huffed|chuckled|countered|finished|began|interrupted|prompted"
)

_PRONOUN_SUBJECTS = r"(?:he|she|they|I|we|you)"
# Subject = pronoun OR a single capitalised name OR "<adj> <Name>" type combo
_SUBJECT = (
    r"(?:" + _PRONOUN_SUBJECTS + r"|"
    r"(?:[A-Z][a-zA-Z'’\-]+(?:\s+[A-Z][a-zA-Z'’\-]+)?)"
    r")"
)
_ADVERB_TAIL = r"(?:\s+(?:[a-z]+ly|softly|quietly|loudly|firmly|under\s+\w+|to\s+\w+(?:\s+\w+)?|at\s+\w+(?:\s+\w+)?))?"

# After-dialogue tag, e.g.  ," she said softly.
_TAG_AFTER = re.compile(
    r"^[\s,]*"
    + _SUBJECT
    + r"\s+(?:" + TAG_VERBS + r")\b"
    + _ADVERB_TAIL,
    re.IGNORECASE,
)

# Before-dialogue tag, e.g.  Sarah said,  "  ...
_TAG_BEFORE = re.compile(
    r"(?:^|[.!?\n])\s*"
    + _SUBJECT
    + r"\s+(?:" + TAG_VERBS + r")\b"
    + _ADVERB_TAIL
    + r"[\s,:]*$",
    re.IGNORECASE,
)

_DIALOGUE_DOUBLE = re.compile(r'"(?P<content>[^"]*)"')
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’\-]*")

_OPEN_PREV = (" ", "\t", "\n", "(", "[", "—", "–", "")
_CLOSE_NEXT = (" ", "\t", "\n", ".", ",", "!", "?", ";", ":", ")", "]", "—", "–", "")


@dataclass
class Breakdown:
    total_words: int
    dialogue_words: int
    narration_words: int
    tag_words: int
    dialogue_lines: int

    @property
    def dialogue_pct(self) -> float:
        return _safe_pct(self.dialogue_words, self.total_words)

    @property
    def narration_pct(self) -> float:
        return _safe_pct(self.narration_words, self.total_words)

    @property
    def tag_pct(self) -> float:
        return _safe_pct(self.tag_words, self.total_words)


def count_words(s: str) -> int:
    return len(_WORD_RE.findall(s))


def recording_time(words: int, words_per_hour: int = DEFAULT_WORDS_PER_HOUR) -> str:
    """Return `H:MM` estimated recording time at the given finished-hour rate."""
    if words_per_hour <= 0 or words <= 0:
        return "0:00"
    minutes_total = round(words * 60 / words_per_hour)
    hours, minutes = divmod(minutes_total, 60)
    return f"{hours}:{minutes:02d}"


def analyze_chapter(chapter: Chapter, mode: str = "auto") -> Breakdown:
    return analyze_text(chapter.text, mode=mode)


def detect_dialogue_mode(text: str) -> str:
    """Pick 'double' or 'single' (UK style) based on which quote pattern dominates."""
    norm = _normalize_quotes(text)
    doubles = len(_DIALOGUE_DOUBLE.findall(norm))
    singles = len(_find_single_dialogue(norm))
    if singles >= 2 and doubles == 0:
        return "single"
    if singles >= 5 and singles >= doubles * 3:
        return "single"
    return "double"


def analyze_text(text: str, mode: str = "auto") -> Breakdown:
    norm = _normalize_quotes(text)
    if mode == "auto":
        mode = detect_dialogue_mode(text)

    if mode == "single":
        spans = _find_single_dialogue(norm)
    else:
        spans = [
            (m.start(), m.end(), m.group("content"))
            for m in _DIALOGUE_DOUBLE.finditer(norm)
        ]

    dialogue_chunks = [content for _, _, content in spans]
    dialogue_words = sum(count_words(d) for d in dialogue_chunks)
    dialogue_lines = sum(1 for d in dialogue_chunks if d.strip())

    interstitials = _interstitials(norm, spans)

    tag_words = 0
    for seg, has_left, has_right in interstitials:
        tag_words += _tag_word_count(seg, has_left, has_right)

    total_narration = sum(count_words(seg) for seg, _, _ in interstitials)
    narration_words = max(0, total_narration - tag_words)

    return Breakdown(
        total_words=dialogue_words + narration_words + tag_words,
        dialogue_words=dialogue_words,
        narration_words=narration_words,
        tag_words=tag_words,
        dialogue_lines=dialogue_lines,
    )


def _normalize_quotes(text: str) -> str:
    return (
        text.replace("“", '"').replace("”", '"')
            .replace("‘", "'").replace("’", "'")
    )


def _interstitials(
    text: str, dialogue_spans: List[Tuple[int, int, str]]
) -> List[Tuple[str, bool, bool]]:
    """Return list of (segment, has_dialogue_to_left, has_dialogue_to_right)."""
    out: List[Tuple[str, bool, bool]] = []
    last = 0
    n = len(dialogue_spans)
    for i, (s, e, _content) in enumerate(dialogue_spans):
        out.append((text[last:s], i > 0, True))
        last = e
    out.append((text[last:], n > 0, False))
    return out


def _find_single_dialogue(text: str) -> List[Tuple[int, int, str]]:
    """Find UK single-quote dialogue spans, skipping intra-word apostrophes.

    Returns a list of (start_idx_of_open_quote, end_idx_after_close_quote, content).
    """
    spans: List[Tuple[int, int, str]] = []
    n = len(text)
    i = 0
    while i < n:
        if text[i] != "'" or not _is_open_single(text, i):
            i += 1
            continue
        # Scan forward for a `'` that looks like a closing quote, allowing
        # intra-word apostrophes (don't, it's) to pass through.
        j = i + 1
        while j < n:
            if text[j] == "'":
                if _is_close_single(text, j):
                    spans.append((i, j + 1, text[i + 1:j]))
                    i = j + 1
                    break
                if _is_apostrophe(text, j):
                    j += 1
                    continue
            if text[j] == "\n" and j + 1 < n and text[j + 1] == "\n":
                # Don't span a paragraph break — bail out of this candidate.
                break
            j += 1
        else:
            i += 1
            continue
        if j >= n:
            i += 1
    return spans


def _is_open_single(text: str, i: int) -> bool:
    prev = text[i - 1] if i > 0 else ""
    nxt = text[i + 1] if i + 1 < len(text) else ""
    if prev not in _OPEN_PREV:
        return False
    return nxt.isalpha() or nxt.isdigit() or nxt in ("—", "–")


def _is_close_single(text: str, i: int) -> bool:
    prev = text[i - 1] if i > 0 else ""
    nxt = text[i + 1] if i + 1 < len(text) else ""
    # Closing must follow a letter/digit/sentence-punct and be followed by
    # whitespace, end of text, or closing punctuation.
    if not (prev.isalnum() or prev in ".,!?;:—–"):
        return False
    return nxt in _CLOSE_NEXT


def _is_apostrophe(text: str, i: int) -> bool:
    prev = text[i - 1] if i > 0 else ""
    nxt = text[i + 1] if i + 1 < len(text) else ""
    # don't, it's, you're → letter-letter; kids' → letter-space (also a possessive)
    return prev.isalpha() and (nxt.isalpha() or nxt == "s")


def _tag_word_count(seg: str, has_left: bool, has_right: bool) -> int:
    """Count words in the dialogue-tag portion(s) of an interstitial segment."""
    counted = 0

    if has_left:
        m = _TAG_AFTER.match(seg)
        if m:
            counted += count_words(m.group(0))
            seg = seg[m.end():]  # don't double-count if same seg also has a "before" tag

    if has_right:
        m = _TAG_BEFORE.search(seg)
        if m:
            counted += count_words(m.group(0))

    return counted


def _safe_pct(num: int, denom: int) -> float:
    return (num / denom * 100.0) if denom else 0.0
