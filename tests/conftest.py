"""Shared pytest fixtures. Test doubles live in ``tests/fakes.py``."""

from __future__ import annotations

import tempfile

import pytest

from app import Config, create_app
from tests.fakes import FakeGateway, FakeTranscriber


@pytest.fixture
def transcriber() -> FakeTranscriber:
    return FakeTranscriber()


@pytest.fixture
def gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture
def config() -> Config:
    # No auth token -> signature validation is disabled, which keeps the
    # webhook-flow tests focused on behavior rather than crypto.
    return Config(twilio_whatsapp_from="whatsapp:+14155238886", trusted_proxies=0)


@pytest.fixture
def app(config: Config, transcriber: FakeTranscriber, gateway: FakeGateway):
    application = create_app(config, transcriber=transcriber, gateway=gateway)
    yield application
    application.extensions["bot"].shutdown()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def audio_file() -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp:
        tmp.write(b"fake audio bytes")
        return tmp.name
