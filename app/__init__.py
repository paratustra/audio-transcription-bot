"""Application factory for the WhatsApp audio-transcription bot."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .services import Services
from .transcription import Transcriber, WhisperTranscriber
from .twilio_gateway import TwilioGateway
from .webhook import bp

__all__ = ["create_app", "Config"]


def create_app(
    config: Config | None = None,
    *,
    transcriber: Transcriber | None = None,
    gateway: TwilioGateway | None = None,
) -> Flask:
    """Build and configure the Flask app.

    Args:
        config: configuration to use; defaults to :meth:`Config.from_env`.
        transcriber: substitute transcriber, mainly for tests. When omitted a
            lazily-loaded :class:`WhisperTranscriber` is created (the model is
            only loaded on first use / ``warm_up``).
        gateway: substitute Twilio gateway, mainly for tests.
    """
    config = config or Config.from_env()

    logging.basicConfig(
        level=logging.DEBUG if config.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = Flask(__name__)
    app.config["BOT_CONFIG"] = config

    if config.trusted_proxies > 0:
        # Honor X-Forwarded-Proto/Host so request.url reflects the public URL
        # Twilio signed — the fix for signature failures behind ngrok/a proxy.
        app.wsgi_app = ProxyFix(  # type: ignore[method-assign]
            app.wsgi_app,
            x_for=config.trusted_proxies,
            x_proto=config.trusted_proxies,
            x_host=config.trusted_proxies,
        )

    services = Services(
        config=config,
        transcriber=transcriber
        or WhisperTranscriber(config.whisper_model, config.whisper_language),
        gateway=gateway or TwilioGateway(config),
        executor=ThreadPoolExecutor(max_workers=1, thread_name_prefix="transcribe"),
    )
    app.extensions["bot"] = services

    if not config.twilio_configured:
        app.logger.warning(
            "Twilio credentials are not fully configured; inbound validation "
            "and outbound messages will not work."
        )

    app.register_blueprint(bp)
    return app
