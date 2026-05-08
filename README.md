# Narrator Friend

A manuscript breakdown tool for audiobook narrators. Drop in a PDF or .docx and get a per-chapter report:

- **Word counts** — total, dialogue, narration, dialogue tags
- **POV detection** — picks up character names used as chapter sub-headers (handy for duet audiobooks)
- **Recording time estimate** — based on a configurable finished-words-per-hour rate (defaults to ACX-style 9,300 wph)
- **Chapter detection** — uses the PDF's bookmarks (or DOCX Heading 1 styles) where present, falls back to heading patterns (`Chapter 1`, `CHAPTER ONE`, `Prologue`, `Part II`…)
- **US + UK quote styles** — auto-detects single-quote (UK) vs double-quote (US) dialogue, including `don't`-style apostrophes inside dialogue.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## CLI

```bash
python -m narrator_friend path/to/manuscript.pdf
python -m narrator_friend manuscript.docx --wph 9500
python -m narrator_friend manuscript.pdf --json > report.json
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
python -m flask --app narrator_friend.web run
# or, for hot-reload during development:
python -m narrator_friend.web
```

Then open <http://127.0.0.1:5000>, drop a PDF, and read the report. The form lets you adjust the words-per-hour rate before analyzing.

Uploads are written to a temporary file, parsed, and deleted — nothing is persisted.

## Tests

```bash
pip install pytest
pytest
```

## How it works

- `narrator_friend/parser.py` — extracts text with `pypdf`, splits into chapters by bookmark or heading regex, strips bare page-number lines, detects POV.
- `narrator_friend/analyzer.py` — finds dialogue spans (curly + straight double quotes), classifies the surrounding interstitial text as either dialogue tags (subject + tag verb adjacent to a quote) or plain narration. Action beats stay narration.
- `narrator_friend/report.py` — aggregates per-chapter breakdowns and totals, computes recording-time estimates.
- `narrator_friend/cli.py` / `narrator_friend/web.py` — thin wrappers around the above.

## Deploying (Vercel)

The repo is set up to deploy as a single Vercel Python serverless function:

- `api/index.py` exposes the Flask `app`
- `vercel.json` rewrites all routes to that function
- Vercel installs `requirements.txt` automatically

Push to the connected repo, or run `vercel --prod`. The Hobby plan caps request bodies at ~4.5 MB, which the upload limit (`MAX_UPLOAD_BYTES`) is set to respect.

## Tip jar

There's no rate limit. The footer of the analysis page shows a Venmo QR / link as a voluntary tip jar. To change the destination, edit `VENMO_URL` and `VENMO_HANDLE` in `narrator_friend/web.py` and regenerate `narrator_friend/static/venmo-qr.svg`:

```bash
python3 - <<'PY'
import qrcode
qr = qrcode.QRCode(version=None, error_correction=qrcode.ERROR_CORRECT_M, box_size=1, border=2)
qr.add_data("https://venmo.com/u/your-handle")
qr.make(fit=True)
m = qr.get_matrix()
size = len(m)
parts = []
for y, row in enumerate(m):
    x = 0
    while x < size:
        if row[x]:
            s = x
            while x < size and row[x]:
                x += 1
            parts.append(f"M{s},{y}h{x-s}v1h-{x-s}z")
        else:
            x += 1
print(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" shape-rendering="crispEdges"><path fill="#000" d="{"".join(parts)}"/></svg>')
PY
```

Pipe that to `narrator_friend/static/venmo-qr.svg`.

## Limitations

- PDFs that are scans rather than text need to be OCR'd first; `pypdf` cannot read images.
- POV detection is conservative — it only fires when the title or first lines look unambiguously like a name.
- UK single-quote detection is best-effort: an unusually apostrophe-heavy passage with no actual dialogue could occasionally trip it (the analyzer falls back to double-quote mode unless there are several clean single-quote dialogue spans).
