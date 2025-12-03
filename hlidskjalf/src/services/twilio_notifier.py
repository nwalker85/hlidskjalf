"""
Twilio notification utility.

Provides a thin wrapper around the official Twilio SDK so the Norns (and
future agents) can deliver SMS/MMS alerts without each caller needing to know
the credential plumbing.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Iterable, Optional

from twilio.rest import Client

from src.core.config import get_settings


class TwilioNotifier:
    """Helper for sending outbound messages through Twilio."""

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: Optional[str] = None,
        messaging_service_sid: Optional[str] = None,
    ) -> None:
        if not account_sid or not auth_token:
            raise ValueError("Twilio credentials are required")

        if not from_number and not messaging_service_sid:
            raise ValueError("Provide either a from number or a messaging service SID")

        self._client = Client(account_sid, auth_token)
        self._from_number = from_number
        self._messaging_service_sid = messaging_service_sid

    def send_message(
        self,
        to_number: str,
        body: str,
        media_urls: Optional[Iterable[str]] = None,
    ) -> str:
        """Send an SMS/MMS message via Twilio and return the message SID."""
        if not to_number:
            raise ValueError("Destination number is required")

        payload: dict[str, object] = {"to": to_number, "body": body}

        if self._messaging_service_sid:
            payload["messaging_service_sid"] = self._messaging_service_sid
        else:
            payload["from_"] = self._from_number

        if media_urls:
            payload["media_url"] = list(media_urls)

        message = self._client.messages.create(**payload)
        return message.sid


@lru_cache
def get_twilio_notifier() -> Optional[TwilioNotifier]:
    """
    Return a memoized Twilio notifier when credentials are present.

    Returns None when Twilio is not configured, allowing callers to degrade gracefully.
    """
    settings = get_settings()

    account_sid = settings.TWILIO_ACCOUNT_SID.strip()
    auth_token = settings.TWILIO_AUTH_TOKEN.strip()
    from_number = settings.TWILIO_FROM_NUMBER.strip() or None
    messaging_service_sid = settings.TWILIO_MESSAGING_SERVICE_SID.strip() or None

    if not account_sid or not auth_token:
        return None

    if not from_number and not messaging_service_sid:
        return None

    return TwilioNotifier(
        account_sid=account_sid,
        auth_token=auth_token,
        from_number=from_number,
        messaging_service_sid=messaging_service_sid,
    )

