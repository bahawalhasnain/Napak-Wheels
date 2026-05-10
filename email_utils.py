"""Lightweight email sender.

Uses SMTP when ``MAIL_SERVER`` is configured. Otherwise just logs the
outgoing message — perfect for local dev. No Flask-Mail dependency.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Iterable

from flask import current_app


logger = logging.getLogger(__name__)


def _truthy(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def send_email(subject: str, body: str, recipients: Iterable[str], html: str | None = None) -> bool:
    """Send an email synchronously. Returns True on success / log-mode."""

    cfg = current_app.config
    server = cfg.get("MAIL_SERVER")
    sender = cfg.get("MAIL_DEFAULT_SENDER", "no-reply@napak-wheels.local")
    recipients = [r for r in recipients if r]

    if not recipients:
        return False

    if not server or cfg.get("MAIL_SUPPRESS_SEND"):
        logger.info(
            "EMAIL (suppressed) to=%s subject=%r body=%s",
            ", ".join(recipients), subject, body[:200],
        )
        return True

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")

    port = int(cfg.get("MAIL_PORT", 587))
    username = cfg.get("MAIL_USERNAME")
    password = cfg.get("MAIL_PASSWORD")
    use_tls = _truthy(cfg.get("MAIL_USE_TLS", True))

    try:
        with smtplib.SMTP(server, port, timeout=15) as smtp:
            smtp.ehlo()
            if use_tls:
                smtp.starttls()
                smtp.ehlo()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(msg)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", recipients)
        return False
