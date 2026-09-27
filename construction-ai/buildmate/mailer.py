"""Outgoing email. Uses SMTP when configured; otherwise logs the message (dev mode)."""
import smtplib
from email.message import EmailMessage

from flask import current_app, flash, render_template
from markupsafe import Markup, escape


def send_email(to, subject, template, dev_link=None, **context):
    cfg = current_app.config
    context.setdefault("app_name", cfg["APP_NAME"])
    text_body = render_template(f"email/{template}.txt", **context)

    if cfg.get("MAIL_SERVER"):
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = cfg["MAIL_FROM"]
        msg["To"] = to
        msg.set_content(text_body)
        try:
            with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=15) as smtp:
                if cfg["MAIL_USE_TLS"]:
                    smtp.starttls()
                if cfg["MAIL_USERNAME"]:
                    smtp.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
                smtp.send_message(msg)
            return True
        except Exception:  # noqa: BLE001 — never crash a user flow on mail failure
            current_app.logger.exception("Failed to send email to %s", to)
            return False

    current_app.logger.warning("[email not sent — no MAIL_SERVER] To: %s | %s\n%s", to, subject, text_body)
    if cfg.get("DEV_SHOW_EMAIL_LINKS") and dev_link:
        flash(
            Markup("Dev mode (no SMTP configured) — email to {} not sent. <a href=\"{}\">Open the link</a>.").format(
                escape(to), escape(dev_link)
            ),
            "dev",
        )
    return False
