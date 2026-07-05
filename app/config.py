"""Application configuration, loaded from environment variables.

All settings live in a single frozen dataclass so they are easy to pass
around, override in tests, and reason about. Nothing here imports Flask,
Twilio, or Whisper, so it stays cheap to import.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

_TRUE = {"1", "true", "yes", "on"}

DEFAULT_MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB, WhatsApp's media ceiling


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in _TRUE


def _as_int(value: str | None, default: int) -> int:
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    """Immutable snapshot of the app's runtime configuration."""

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""

    whisper_model: str = "small"
    whisper_language: str | None = None

    # When set, signatures are validated against this base URL instead of the
    # (proxy-dependent) reconstructed request URL. This is the most robust
    # option behind ngrok / a load balancer, where the scheme Twilio signed
    # (https) differs from the scheme Flask sees (http).
    public_base_url: str | None = None

    # Number of proxies in front of the app that ProxyFix should trust for
    # X-Forwarded-* headers. 0 disables ProxyFix.
    trusted_proxies: int = 1

    # Reply immediately with an ack and deliver the transcription in a second
    # message via the REST API, instead of holding the webhook open.
    async_reply: bool = False

    max_audio_bytes: int = DEFAULT_MAX_AUDIO_BYTES
    download_timeout: int = 60

    debug: bool = False
    port: int = 5000

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Config:
        env = os.environ if env is None else env
        language = env.get("WHISPER_LANGUAGE") or None
        public_base_url = env.get("PUBLIC_BASE_URL") or None
        return cls(
            twilio_account_sid=env.get("TWILIO_ACCOUNT_SID", ""),
            twilio_auth_token=env.get("TWILIO_AUTH_TOKEN", ""),
            twilio_whatsapp_from=env.get("TWILIO_WHATSAPP_FROM", ""),
            whisper_model=env.get("WHISPER_MODEL", "small"),
            whisper_language=language,
            public_base_url=public_base_url,
            trusted_proxies=_as_int(env.get("TRUSTED_PROXIES"), 1),
            async_reply=_as_bool(env.get("ASYNC_REPLY")),
            max_audio_bytes=_as_int(env.get("MAX_AUDIO_BYTES"), DEFAULT_MAX_AUDIO_BYTES),
            download_timeout=_as_int(env.get("DOWNLOAD_TIMEOUT"), 60),
            debug=_as_bool(env.get("DEBUG")),
            port=_as_int(env.get("PORT"), 5000),
        )

    @property
    def twilio_configured(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token)

    @property
    def can_send_outbound(self) -> bool:
        return self.twilio_configured and bool(self.twilio_whatsapp_from)
