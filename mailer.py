#!/usr/bin/env python3
"""Lightweight email sender for Cloud Run notifications."""

from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path


@dataclass(frozen=True)
class MailConfig:
    enabled: bool
    backend: str
    host: str
    port: int
    username: str
    password: str
    mail_from: str
    mail_to: str
    use_tls: bool


def load_mail_config() -> MailConfig:
    backend = _env("MAIL_BACKEND", "smtp").lower()
    mail_to = _env("MAIL_TO", "")
    enabled = backend in {"smtp", "gmail_smtp"} and bool(mail_to)
    host = _env("SMTP_HOST", "smtp.gmail.com")
    port = int(_env("SMTP_PORT", "587"))
    username = _env("SMTP_USERNAME", "")
    password = _env("SMTP_PASSWORD", "")
    mail_from = _env("MAIL_FROM", username or "")
    use_tls = _env_bool("SMTP_USE_TLS", True)
    return MailConfig(
        enabled=enabled,
        backend=backend,
        host=host,
        port=port,
        username=username,
        password=password,
        mail_from=mail_from,
        mail_to=mail_to,
        use_tls=use_tls,
    )


def send_notification_email(
    *,
    subject: str,
    body: str,
    html_body: str | None = None,
    attachments: list[Path] | None = None,
) -> bool:
    config = load_mail_config()
    if not config.enabled:
        print("MAIL_TO not set or MAIL_BACKEND disabled; skipping email notification.", flush=True)
        return False
    if not config.mail_from:
        raise RuntimeError("MAIL_FROM or SMTP_USERNAME must be set for email sending.")
    if not config.username or not config.password:
        raise RuntimeError("SMTP_USERNAME and SMTP_PASSWORD are required for email sending.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.mail_from
    message["To"] = config.mail_to
    message.set_content(body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    for attachment in attachments or []:
        path = Path(attachment)
        if not path.exists() or not path.is_file():
            continue
        maintype, subtype = _mime_type_for(path.suffix.lower())
        message.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)

    print(f"Sending email to {config.mail_to} via {config.host}:{config.port}...", flush=True)
    with smtplib.SMTP(config.host, config.port, timeout=30) as client:
        if config.use_tls:
            client.starttls()
        client.login(config.username, config.password)
        client.send_message(message)
    print("Email notification sent.", flush=True)
    return True


def _mime_type_for(suffix: str) -> tuple[str, str]:
    return {
        ".html": ("text", "html"),
        ".txt": ("text", "plain"),
        ".md": ("text", "markdown"),
        ".json": ("application", "json"),
        ".svg": ("image", "svg+xml"),
        ".png": ("image", "png"),
        ".jpg": ("image", "jpeg"),
        ".jpeg": ("image", "jpeg"),
        ".pdf": ("application", "pdf"),
    }.get(suffix, ("application", "octet-stream"))


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name, "true" if default else "false").lower()
    return raw in {"1", "true", "yes", "on"}
