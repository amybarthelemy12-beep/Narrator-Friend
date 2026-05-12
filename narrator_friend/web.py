"""Tiny Flask web UI: drop a manuscript (PDF or .docx), get a report."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from flask import Flask, render_template, request

from .analyzer import DEFAULT_WORDS_PER_HOUR
from .costs import (
    DEFAULT_EDITING_RATE,
    DEFAULT_EXPERIENCE,
    DEFAULT_NARRATOR_RATE,
    DEFAULT_PROOFING_RATE,
    EXPERIENCE_RATES,
)
from .parser import SUPPORTED_EXTENSIONS, parse_manuscript
from .report import build_report

MAX_UPLOAD_BYTES = 4 * 1024 * 1024  # 4 MB — Vercel hobby request-body cap is 4.5 MB
VENMO_URL = "https://venmo.com/u/Amy-barthelemy12"
VENMO_HANDLE = "@Amy-barthelemy12"


def _float_or(default: float, raw: str | None, lo: float = 0.0, hi: float = 10000.0) -> float:
    try:
        v = float(raw) if raw not in (None, "") else default
    except ValueError:
        v = default
    return max(lo, min(v, hi))


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    def _render(
        report=None,
        error=None,
        wph=DEFAULT_WORDS_PER_HOUR,
        filename=None,
        experience=DEFAULT_EXPERIENCE,
        narrator_rate=DEFAULT_NARRATOR_RATE,
        editing_rate=DEFAULT_EDITING_RATE,
        proofing_rate=DEFAULT_PROOFING_RATE,
        proofing_on=False,
        status=200,
    ):
        return render_template(
            "index.html",
            report=report,
            error=error,
            words_per_hour=wph,
            filename=filename,
            venmo_url=VENMO_URL,
            venmo_handle=VENMO_HANDLE,
            experience=experience,
            experience_rates=EXPERIENCE_RATES,
            narrator_rate=narrator_rate,
            editing_rate=editing_rate,
            proofing_rate=proofing_rate,
            proofing_on=proofing_on,
        ), status

    @app.get("/")
    def index():
        body, _status = _render()
        return body

    @app.post("/analyze")
    def analyze():
        upload = request.files.get("manuscript")
        if not upload or not upload.filename:
            return _render(error="Please choose a PDF or Word file.", status=400)

        suffix = Path(upload.filename).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            return _render(
                error="Please upload a .pdf or .docx file (Word for the web works — just save as .docx first).",
                status=400,
            )

        try:
            wph = int(request.form.get("wph") or DEFAULT_WORDS_PER_HOUR)
        except ValueError:
            wph = DEFAULT_WORDS_PER_HOUR
        wph = max(1000, min(wph, 30000))

        experience = request.form.get("experience") or DEFAULT_EXPERIENCE
        if experience not in EXPERIENCE_RATES:
            experience = DEFAULT_EXPERIENCE
        preset_rate = EXPERIENCE_RATES[experience]

        narrator_rate = _float_or(preset_rate, request.form.get("narrator_rate"), lo=0.0, hi=2000.0)
        editing_rate = _float_or(DEFAULT_EDITING_RATE, request.form.get("editing_rate"), lo=0.0, hi=2000.0)
        proofing_rate = _float_or(DEFAULT_PROOFING_RATE, request.form.get("proofing_rate"), lo=0.0, hi=2000.0)
        proofing_on = bool(request.form.get("proofing_on"))

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name
            upload.save(tmp_path)

        try:
            chapters = parse_manuscript(tmp_path)
            report = build_report(chapters, words_per_hour=wph)
        except Exception as exc:
            return _render(
                error=f"Couldn't read that file: {exc}",
                wph=wph,
                filename=upload.filename,
                experience=experience,
                narrator_rate=narrator_rate,
                editing_rate=editing_rate,
                proofing_rate=proofing_rate,
                proofing_on=proofing_on,
                status=400,
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        body, _status = _render(
            report=report,
            wph=wph,
            filename=upload.filename,
            experience=experience,
            narrator_rate=narrator_rate,
            editing_rate=editing_rate,
            proofing_rate=proofing_rate,
            proofing_on=proofing_on,
        )
        return body

    @app.errorhandler(413)
    def too_large(_exc):
        body, status = _render(
            error=f"File is too big — max upload is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
            status=413,
        )
        return body, status

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
