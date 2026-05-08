# Crystal

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
python -m crystal path/to/manuscript.pdf
python -m crystal manuscript.docx --wph 9500
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

## Deploying (Vercel)

The repo is set up to deploy as a single Vercel Python serverless function:

- `api/index.py` exposes the Flask `app`
- `vercel.json` rewrites all routes to that function
- Vercel installs `requirements.txt` automatically

Push to the connected repo, or run `vercel --prod`. The Hobby plan caps request bodies at ~4.5 MB, which the upload limit (`MAX_UPLOAD_BYTES`) is set to respect.

### Environment variables

Set these in the Vercel project's **Settings → Environment Variables**:

| Var | Required | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | **yes** on Vercel | Signs the Flask session cookie that holds the rate-limit + paid-credit state. Use any long random string (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`). Without it, sessions reset on every cold start and the rate limit is effectively off. |
| `STRIPE_SECRET_KEY` | optional | Stripe live/test secret key. When unset, the paywall page shows a "launching soon" placeholder. |
| `STRIPE_PRICE_ID` | optional | Stripe price ID for the $0.99 per-report product. Required alongside `STRIPE_SECRET_KEY` to enable real checkout. |
| `UNLOCK_KEY` | optional | A private string. Visiting `/unlock/<value>` once grants the current browser unlimited reports. Useful for you and Crystal to bypass the paywall. |

### Pay-per-report

The first analysis per browser session is free; further analyses require a $0.99 Stripe Checkout payment. After a successful payment Stripe redirects to `/paid?session_id=…`, the server verifies the session, and grants one paid credit. Each credit is consumed by the next successful analysis.

## Limitations

- PDFs that are scans rather than text need to be OCR'd first; `pypdf` cannot read images.
- POV detection is conservative — it only fires when the title or first lines look unambiguously like a name.
- UK single-quote detection is best-effort: an unusually apostrophe-heavy passage with no actual dialogue could occasionally trip it (the analyzer falls back to double-quote mode unless there are several clean single-quote dialogue spans).
