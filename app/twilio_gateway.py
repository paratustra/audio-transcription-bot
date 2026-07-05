"""All interaction with Twilio: signature validation, media download, sending.

Signature validation is the subtle part. Twilio signs the exact public URL you
configured (typically ``https://...``). Behind ngrok or a load balancer, TLS is
terminated at the edge and Flask sees plain ``http``, so a signature computed
over the app's view of the URL will not match. We handle this two ways:

* ``PUBLIC_BASE_URL`` (preferred, most robust): rebuild the signed URL from a
  trusted, statically-configured base — proxy headers can be spoofed.
* otherwise trust ``X-Forwarded-Proto`` via Werkzeug's ProxyFix (wired up in the
  app factory) so ``request.url`` already reflects the public scheme/host.
"""

from __future__ import annotations

import contextlib
import logging
import os
import tempfile
from dataclasses import dataclass

import requests
from flask import Request
from twilio.base.exceptions import TwilioRestException
from twilio.request_validator import RequestValidator
from twilio.rest import Client

from .config import Config

logger = logging.getLogger(__name__)


class MediaTooLargeError(Exception):
    """Raised when a media download exceeds the configured size limit."""


@dataclass(frozen=True)
class Media:
    path: str
    content_type: str | None


def _with_whatsapp_prefix(number: str) -> str:
    return number if number.startswith("whatsapp:") else f"whatsapp:{number}"


class TwilioGateway:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._validator = (
            RequestValidator(config.twilio_auth_token) if config.twilio_auth_token else None
        )
        self._client = (
            Client(config.twilio_account_sid, config.twilio_auth_token)
            if config.twilio_configured
            else None
        )

    # -- signature validation ------------------------------------------------

    @property
    def enforces_signatures(self) -> bool:
        return self._validator is not None

    def _signed_url(self, request: Request) -> str:
        base = self._config.public_base_url
        if not base:
            # ProxyFix has already corrected request.url from X-Forwarded-*.
            return request.url
        url = base.rstrip("/") + request.path
        if request.query_string:
            url += "?" + request.query_string.decode()
        return url

    def is_valid_signature(self, request: Request) -> bool:
        if self._validator is None:
            # No auth token configured: cannot validate. Callers decide policy.
            return False
        signature = request.headers.get("X-Twilio-Signature", "")
        # Pass request.form unmodified — the validator sorts params itself.
        return self._validator.validate(self._signed_url(request), request.form, signature)

    # -- media ---------------------------------------------------------------

    def download_media(self, media_url: str, content_type: str | None) -> Media:
        """Download inbound media to a temp file, enforcing the size limit.

        Twilio media URLs are Basic-auth protected (account SID / auth token)
        and 302-redirect to a pre-signed CDN URL; ``requests`` drops the auth
        header on that cross-host hop, which is exactly what we want.
        """
        auth = (
            (self._config.twilio_account_sid, self._config.twilio_auth_token)
            if self._config.twilio_configured
            else None
        )
        limit = self._config.max_audio_bytes
        suffix = _suffix_for(content_type)

        # delete=False: we hand the path to the caller, who removes it after use.
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)  # noqa: SIM115
        downloaded = 0
        try:
            with requests.get(
                media_url,
                stream=True,
                timeout=self._config.download_timeout,
                auth=auth,
            ) as response:
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    downloaded += len(chunk)
                    if downloaded > limit:
                        raise MediaTooLargeError(f"media exceeds {limit} bytes")
                    tmp.write(chunk)
            tmp.close()
            return Media(path=tmp.name, content_type=content_type)
        except Exception:
            tmp.close()
            _safe_remove(tmp.name)
            raise

    # -- outbound ------------------------------------------------------------

    def send_whatsapp(self, to: str, body: str) -> bool:
        if self._client is None or not self._config.twilio_whatsapp_from:
            logger.error("Cannot send outbound message: Twilio client or sender not configured")
            return False
        try:
            self._client.messages.create(
                body=body,
                from_=_with_whatsapp_prefix(self._config.twilio_whatsapp_from),
                to=_with_whatsapp_prefix(to),
            )
            return True
        except TwilioRestException:
            logger.exception("Failed to send outbound WhatsApp message")
            return False


def _suffix_for(content_type: str | None) -> str:
    if not content_type:
        return ".tmp"
    subtype = content_type.split("/", 1)[-1].split(";", 1)[0].strip().lower()
    known = {"ogg", "mpeg", "mp3", "mp4", "wav", "webm", "amr", "aac", "m4a", "flac"}
    return f".{subtype}" if subtype in known else ".tmp"


def _safe_remove(path: str) -> None:
    with contextlib.suppress(OSError):
        os.remove(path)
