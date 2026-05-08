"""Tiny Flask web UI: drop a manuscript (PDF or .docx), get a report."""

from __future__ import annotations

import os
import secrets
import tempfile
from datetime import timedelta
from pathlib import Path

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .analyzer import DEFAULT_WORDS_PER_HOUR
from .parser import SUPPORTED_EXTENSIONS, parse_manuscript
from .report import build_report

MAX_UPLOAD_BYTES = 4 * 1024 * 1024  # 4 MB — Vercel hobby request-body cap is 4.5 MB
FREE_UPLOADS = 1
PRICE_DISPLAY = "$0.99"
SESSION_LIFETIME_DAYS = 365


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    app.permanent_session_lifetime = timedelta(days=SESSION_LIFETIME_DAYS)
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = bool(os.environ.get("VERCEL"))
    app.secret_key = _resolve_secret_key()

    @app.before_request
    def _persist_session():
        session.permanent = True

    # --- credit accounting -------------------------------------------------

    def _has_unlimited() -> bool:
        return bool(session.get("unlimited"))

    def _free_remaining() -> int:
        return max(0, FREE_UPLOADS - int(session.get("free_used", 0)))

    def _paid_remaining() -> int:
        return int(session.get("paid_credits", 0))

    def _credits_remaining() -> int:
        if _has_unlimited():
            return 9999
        return _free_remaining() + _paid_remaining()

    def _consume_credit() -> None:
        if _has_unlimited():
            return
        if _free_remaining() > 0:
            session["free_used"] = int(session.get("free_used", 0)) + 1
        elif _paid_remaining() > 0:
            session["paid_credits"] = _paid_remaining() - 1
        session.modified = True

    def _credit_paid_session(stripe_session_id: str) -> bool:
        """Idempotently grant 1 paid credit per Stripe checkout session."""
        consumed = list(session.get("consumed_session_ids", []))
        if stripe_session_id in consumed:
            return False
        session["paid_credits"] = _paid_remaining() + 1
        consumed.append(stripe_session_id)
        session["consumed_session_ids"] = consumed[-20:]  # cap cookie size
        session.modified = True
        return True

    # --- views -------------------------------------------------------------

    def _render(report=None, error=None, wph=DEFAULT_WORDS_PER_HOUR, filename=None, status=200):
        return render_template(
            "index.html",
            report=report,
            error=error,
            words_per_hour=wph,
            filename=filename,
            credits_remaining=_credits_remaining(),
            unlimited=_has_unlimited(),
            price_display=PRICE_DISPLAY,
        ), status

    @app.get("/")
    def index():
        body, _status = _render()
        return body

    @app.post("/analyze")
    def analyze():
        if not _has_unlimited() and _credits_remaining() <= 0:
            return redirect(url_for("paywall"))

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

        _consume_credit()

        body, _status = _render(report=report, wph=wph, filename=upload.filename)
        return body

    @app.get("/paywall")
    def paywall():
        return render_template(
            "paywall.html",
            stripe_configured=_stripe_configured(),
            price_display=PRICE_DISPLAY,
            credits_remaining=_credits_remaining(),
        )

    @app.post("/checkout")
    def checkout():
        if not _stripe_configured():
            return redirect(url_for("paywall"))
        import stripe

        stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
        host = request.host_url.rstrip("/")
        try:
            checkout_session = stripe.checkout.Session.create(
                mode="payment",
                line_items=[{"price": os.environ["STRIPE_PRICE_ID"], "quantity": 1}],
                success_url=f"{host}/paid?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{host}/paywall",
            )
        except Exception as exc:  # surface Stripe errors to the user
            body, _status = _render(
                error=f"Couldn't open checkout: {exc}",
                status=500,
            )
            return body, 500
        return redirect(checkout_session.url, code=303)

    @app.get("/paid")
    def paid():
        sid = request.args.get("session_id")
        if not sid or not _stripe_configured():
            return redirect(url_for("index"))
        import stripe

        stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
        try:
            cs = stripe.checkout.Session.retrieve(sid)
        except Exception:
            return redirect(url_for("paywall"))
        if getattr(cs, "payment_status", None) == "paid":
            _credit_paid_session(sid)
        return redirect(url_for("index"))

    @app.get("/unlock/<token>")
    def unlock(token: str):
        expected = os.environ.get("UNLOCK_KEY")
        if not expected or not secrets.compare_digest(token, expected):
            abort(404)
        session["unlimited"] = True
        session.modified = True
        return redirect(url_for("index"))

    @app.errorhandler(413)
    def too_large(_exc):
        body, status = _render(
            error=f"File is too big — max upload is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
            status=413,
        )
        return body, status

    return app


def _resolve_secret_key() -> str:
    secret = os.environ.get("SECRET_KEY")
    if secret:
        return secret
    if os.environ.get("VERCEL"):
        # On Vercel, a random per-cold-start key would invalidate every session
        # at the next instance boot. Fail loud so the operator sets SECRET_KEY.
        print(
            "WARNING: SECRET_KEY env var is not set on Vercel. "
            "Sessions (and the rate-limit) will reset on every cold start.",
            flush=True,
        )
        return "crystal-set-SECRET_KEY-env-var"
    # Local dev fallback — fine because the process is long-lived.
    return secrets.token_hex(32)


def _stripe_configured() -> bool:
    return bool(os.environ.get("STRIPE_SECRET_KEY") and os.environ.get("STRIPE_PRICE_ID"))


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
