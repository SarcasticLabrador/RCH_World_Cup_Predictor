"""Email sending: a tiny provider abstraction.

- ConsoleEmailSender: development default. Logs the message (and magic link)
  so the whole auth flow is testable without any API key.
- BrevoEmailSender: posts to the Brevo transactional API using a single
  verified sender (no domain/DNS required).

Select via EMAIL_PROVIDER ("console" | "brevo").
"""
from __future__ import annotations

import logging

import httpx

from backend.config import Settings, get_settings

logger = logging.getLogger("worldcup.email")

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"


class EmailSender:
    def send(self, to_email: str, subject: str, html: str, text: str) -> None:
        raise NotImplementedError


class ConsoleEmailSender(EmailSender):
    def send(self, to_email: str, subject: str, html: str, text: str) -> None:
        logger.info(
            "\n--- EMAIL (console) ---\nTo: %s\nSubject: %s\n%s\n-----------------------",
            to_email,
            subject,
            text,
        )


class BrevoEmailSender(EmailSender):
    def __init__(self, api_key: str, from_email: str, from_name: str):
        if not api_key or not from_email:
            raise ValueError("Brevo provider requires BREVO_API_KEY and EMAIL_FROM")
        self._api_key = api_key
        self._from_email = from_email
        self._from_name = from_name

    def send(self, to_email: str, subject: str, html: str, text: str) -> None:
        payload = {
            "sender": {"email": self._from_email, "name": self._from_name},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html,
            "textContent": text,
        }
        headers = {"api-key": self._api_key, "content-type": "application/json"}
        resp = httpx.post(BREVO_ENDPOINT, json=payload, headers=headers, timeout=15.0)
        resp.raise_for_status()


def get_email_sender(settings: Settings | None = None) -> EmailSender:
    settings = settings or get_settings()
    if settings.email_provider.lower() == "brevo":
        return BrevoEmailSender(
            api_key=settings.brevo_api_key,
            from_email=settings.email_from,
            from_name=settings.email_from_name,
        )
    return ConsoleEmailSender()
