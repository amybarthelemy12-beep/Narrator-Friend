"""Tiny Flask web UI: drop a manuscript (PDF or .docx), get a report."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from flask import Flask, render_template, request

from .analyzer import DEFAULT_WORDS_PER_HOUR
from .parser import SUPPORTED_EXTENSIONS, parse_manuscript
from .report import build_report

MAX_UPLOAD_BYTES = 4 * 1024 * 1024  # 4 MB — Vercel hobby request-body cap is 4.5 MB


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    def _render(report=None, error=None, wph=DEFAULT_WORDS_PER_HOUR, filename=None, status=200):
        return render_template(
            "index.html",
            report=report,
            error=error,
            words_per_hour=wph,
            filename=filename,
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
                status=400,
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        body, _status = _render(report=report, wph=wph, filename=upload.filename)
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
