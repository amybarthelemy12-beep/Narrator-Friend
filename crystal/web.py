"""Tiny Flask web UI: drop a PDF, get a report."""

from __future__ import annotations

import os
import tempfile

from flask import Flask, render_template, request

from .analyzer import DEFAULT_WORDS_PER_HOUR
from .parser import parse_pdf
from .report import build_report

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            report=None,
            error=None,
            words_per_hour=DEFAULT_WORDS_PER_HOUR,
            filename=None,
        )

    @app.post("/analyze")
    def analyze():
        upload = request.files.get("manuscript")
        if not upload or not upload.filename:
            return render_template(
                "index.html",
                report=None,
                error="Please choose a PDF file.",
                words_per_hour=DEFAULT_WORDS_PER_HOUR,
                filename=None,
            ), 400

        if not upload.filename.lower().endswith(".pdf"):
            return render_template(
                "index.html",
                report=None,
                error="That doesn't look like a PDF. Please upload a .pdf file.",
                words_per_hour=DEFAULT_WORDS_PER_HOUR,
                filename=None,
            ), 400

        try:
            wph = int(request.form.get("wph") or DEFAULT_WORDS_PER_HOUR)
        except ValueError:
            wph = DEFAULT_WORDS_PER_HOUR
        wph = max(1000, min(wph, 30000))

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
            upload.save(tmp_path)

        try:
            chapters = parse_pdf(tmp_path)
            report = build_report(chapters, words_per_hour=wph)
        except Exception as exc:  # surface a useful message
            return render_template(
                "index.html",
                report=None,
                error=f"Couldn't parse that PDF: {exc}",
                words_per_hour=wph,
                filename=upload.filename,
            ), 400
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return render_template(
            "index.html",
            report=report,
            error=None,
            words_per_hour=wph,
            filename=upload.filename,
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
