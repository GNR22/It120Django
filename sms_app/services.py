"""
TextBee integration layer.

Everything that talks to the SMS provider lives here so the views stay small
and the provider could be swapped without touching them.

Security notes
--------------
* Credentials are read from Django settings (which read environment variables).
* Credentials are never logged and never included in user-facing messages.
* Raw provider exceptions are translated into short, safe messages.
"""
import logging
from dataclasses import dataclass

from django.conf import settings
from textbee import Textbee, TextbeeError

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Exceptions
# --------------------------------------------------------------------------
class SMSError(Exception):
    """Base class. ``user_message`` is always safe to show to the user."""

    def __init__(self, user_message, code=""):
        super().__init__(user_message)
        self.user_message = user_message
        self.code = str(code) if code else ""


class SMSConfigurationError(SMSError):
    """Credentials are missing or were rejected."""


class SMSConnectionError(SMSError):
    """The provider could not be reached (network problem, timeout, ...)."""


class SMSProviderError(SMSError):
    """The provider answered but refused or failed the request."""


# --------------------------------------------------------------------------
# Result objects
# --------------------------------------------------------------------------
@dataclass
class SendResult:
    sid: str
    status: str


@dataclass
class StatusResult:
    status: str
    error_code: str
    error_message: str


def _translate_rejection(exc):
    """Convert a TextbeeError into one of our safe SMSError types."""
    status = exc.status
    if status in (401, 403):
        return SMSConfigurationError(
            "TextBee rejected the API key. Check TEXTBEE_API_KEY in the .env file.",
            code=status,
        )
    if status == 429:
        return SMSProviderError(
            "TextBee is rate-limiting requests. Please wait a moment and try again.",
            code=status,
        )
    message = (
        "TextBee could not complete the request"
        + (f" (status {status})" if status else "")
        + ". Please try again or check your TextBee dashboard."
    )
    return SMSProviderError(message, code=status)


# --------------------------------------------------------------------------
# Client construction
# --------------------------------------------------------------------------
def _get_client():
    """Build a TextBee client, or raise SMSConfigurationError if not configured."""
    api_key = (settings.TEXTBEE_API_KEY or "").strip()
    if not api_key:
        raise SMSConfigurationError(
            "SMS sending is not configured yet. Set TEXTBEE_API_KEY in the .env file."
        )
    return Textbee(api_key=api_key)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def send_sms(to, body):
    """Submit one SMS to TextBee. Returns SendResult or raises SMSError.

    A returned SendResult means TextBee ACCEPTED the request. It does not mean
    the phone has received the message.
    """
    client = _get_client()

    try:
        result = client.send_sms(recipients=[to], message=body)
    except TextbeeError as exc:
        logger.warning("TextBee rejected a message: status=%s", exc.status)
        raise _translate_rejection(exc) from exc
    except OSError as exc:
        logger.warning("Could not reach TextBee: %s", type(exc).__name__)
        raise SMSConnectionError(
            "Could not reach TextBee. Check your internet connection and try again."
        ) from exc
    except Exception as exc:  # last-resort guard so users never see a stack trace
        logger.exception("Unexpected error while sending SMS")
        raise SMSProviderError(
            "An unexpected error occurred while sending the message. "
            "Please try again."
        ) from exc

    batch_id = result.get("smsBatchId") or ""
    status = "pending" if batch_id else "dispatched"
    return SendResult(sid=batch_id, status=status)


def fetch_status(sid):
    """Ask TextBee for the latest status of a previously submitted batch."""
    client = _get_client()
    try:
        page = client.get_messages(sms_batch_id=sid)
    except TextbeeError as exc:
        logger.warning("TextBee status lookup failed: status=%s", exc.status)
        raise _translate_rejection(exc) from exc
    except OSError as exc:
        logger.warning("Could not reach TextBee: %s", type(exc).__name__)
        raise SMSConnectionError(
            "Could not reach TextBee. Check your internet connection and try again."
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error while fetching message status")
        raise SMSProviderError(
            "An unexpected error occurred while checking the message status."
        ) from exc

    batch_messages = page.get("data", [])
    if not batch_messages:
        return StatusResult(status="unknown", error_code="", error_message="")

    msg = batch_messages[0]
    return StatusResult(
        status=(msg.get("status") or "unknown")[:30],
        error_code=str(msg.get("errorCode") or "")[:20],
        error_message=(msg.get("errorMessage") or "")[:300],
    )
