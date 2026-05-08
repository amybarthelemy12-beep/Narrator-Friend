"""Vercel Python serverless entry point — exposes the Flask `app`."""

import sys
from pathlib import Path

# Make sure the project root (one level above /api) is importable so we can
# load the `narrator_friend` package from the serverless function.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from narrator_friend.web import app  # noqa: E402  (sys.path tweak must come first)
