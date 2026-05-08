# Crystal

A manuscript breakdown tool for audiobook narrators. Drop in a PDF, get a per-chapter report:

- **Word counts** — total, dialogue, narration, dialogue tags
- **POV detection** — picks up character names used as chapter sub-headers (handy for duet audiobooks)
- **Recording time estimate** — based on a configurable finished-words-per-hour rate (defaults to ACX-style 9,300 wph)
- **Chapter detection** — uses the PDF's bookmarks where present, falls back to heading patterns (`Chapter 1`, `CHAPTER ONE`, `Prologue`, `Part II`…)

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## CLI

```bash
python -m crystal path/to/manuscript.pdf
python -m crystal manuscript.pdf --wph 9500
python -m crystal manuscript.pdf --json > report.json
```

Example output:

```
  #    Pg  Title                                   POV             Words   Dial   Narr  Tags    Time
  ----------------------------------------------------------------------------------------------------
  1     1  Chapter 1                               Sarah            3421    34%    61%    5%   0:22
  2    18  Chapter 2                               Jack             2890    41%    54%    5%   0:19
  ...
```

## Web app

```bash
python -m flask --app crystal.web run
# or, for hot-reload during development:
python -m crystal.web
```

Then open <http://127.0.0.1:5000>, drop a PDF, and read the report. The form lets you adjust the words-per-hour rate before analyzing.

Uploads are written to a temporary file, parsed, and deleted — nothing is persisted.

## Tests

```bash
pip install pytest
pytest
```

## How it works

- `crystal/parser.py` — extracts text with `pypdf`, splits into chapters by bookmark or heading regex, strips bare page-number lines, detects POV.
- `crystal/analyzer.py` — finds dialogue spans (curly + straight double quotes), classifies the surrounding interstitial text as either dialogue tags (subject + tag verb adjacent to a quote) or plain narration. Action beats stay narration.
- `crystal/report.py` — aggregates per-chapter breakdowns and totals, computes recording-time estimates.
- `crystal/cli.py` / `crystal/web.py` — thin wrappers around the above.

## Limitations

- Heuristic dialogue detection assumes double-quote-delimited dialogue. UK-style single-quote dialogue is not supported in this version.
- PDFs that are scans rather than text need to be OCR'd first; `pypdf` cannot read images.
- POV detection is conservative — it only fires when the title or first lines look unambiguously like a name.
