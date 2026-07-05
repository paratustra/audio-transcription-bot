"""HTTP surface: a health check and the Twilio WhatsApp webhook."""

from __future__ import annotations

import contextlib
import logging
import os

from flask import Blueprint, Response, current_app, request
from twilio.twiml.messaging_response import MessagingResponse

from .services import Services
from .twilio_gateway import Media, MediaTooLargeError

logger = logging.getLogger(__name__)

bp = Blueprint("webhook", __name__)

HELP_TEXT = (
    "Send a WhatsApp voice note or audio file and I'll transcribe it. "
    "Supported formats: audio/* (e.g. OGG/Opus voice notes)."
)


def _services() -> Services:
    return current_app.extensions["bot"]


def _twiml(*messages: str) -> Response:
    # Always 200: Twilio discards the TwiML body on a non-2xx status, so even
    # error replies are returned as 200 to reach the user.
    response = MessagingResponse()
    for message in messages:
        response.message(message)
    return Response(str(response), mimetype="application/xml")


@bp.get("/")
@bp.get("/healthz")
def health() -> tuple[str, int]:
    return "ok", 200


@bp.post("/whatsapp")
def whatsapp() -> Response:
    services = _services()
    gateway = services.gateway

    if gateway.enforces_signatures:
        if not gateway.is_valid_signature(request):
            logger.warning("Rejected request with invalid Twilio signature")
            return Response("Invalid signature", status=403)
    else:
        logger.warning(
            "Twilio auth token not configured; skipping signature validation. "
            "Do not run like this in production."
        )

    from_number = request.form.get("From", "")
    num_media = _int(request.form.get("NumMedia"))
    if num_media == 0:
        return _twiml(HELP_TEXT)

    content_type = request.form.get("MediaContentType0")
    media_url = request.form.get("MediaUrl0")
    if not _is_audio(content_type) or not media_url:
        return _twiml("Please send an audio message — that media isn't recognized as audio.")

    try:
        media = gateway.download_media(media_url, content_type)
    except MediaTooLargeError:
        return _twiml("That audio is too large for me to process. Please send a shorter clip.")
    except Exception:
        logger.exception("Failed to download media")
        # Return 200 so Twilio delivers this TwiML reply — a non-2xx status
        # makes Twilio discard the body, and the user would hear nothing back.
        return _twiml("Sorry, I couldn't download that audio. Please try again.")

    if services.config.async_reply and from_number and services.config.can_send_outbound:
        services.submit(_transcribe_and_reply, services, media, from_number)
        return _twiml("Got your audio — transcribing now, I'll reply shortly. 🎧")

    try:
        text = services.transcriber.transcribe(media.path) or "(no speech detected)"
    except Exception:
        logger.exception("Transcription failed")
        return _twiml("Sorry, there was an error transcribing your audio.")
    finally:
        _remove(media)
    return _twiml(text)


def _transcribe_and_reply(services: Services, media: Media, to_number: str) -> None:
    try:
        text = services.transcriber.transcribe(media.path) or "(no speech detected)"
        services.gateway.send_whatsapp(to_number, text)
    except Exception:
        logger.exception("Background transcription failed")
        services.gateway.send_whatsapp(
            to_number, "Sorry, there was an error transcribing your audio."
        )
    finally:
        _remove(media)


def _is_audio(content_type: str | None) -> bool:
    return bool(content_type) and content_type.lower().startswith("audio/")


def _int(value: str | None) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def _remove(media: Media) -> None:
    with contextlib.suppress(OSError):
        os.remove(media.path)
