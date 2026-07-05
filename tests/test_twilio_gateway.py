import os

import pytest
from twilio.request_validator import RequestValidator

from app.config import Config
from app.twilio_gateway import (
    MediaTooLargeError,
    TwilioGateway,
    _suffix_for,
    _with_whatsapp_prefix,
)


def test_whatsapp_prefix():
    assert _with_whatsapp_prefix("+14155238886") == "whatsapp:+14155238886"
    assert _with_whatsapp_prefix("whatsapp:+14155238886") == "whatsapp:+14155238886"


def test_suffix_for_content_type():
    assert _suffix_for("audio/ogg") == ".ogg"
    assert _suffix_for("audio/mpeg; codecs=x") == ".mpeg"
    assert _suffix_for("application/octet-stream") == ".tmp"
    assert _suffix_for(None) == ".tmp"


def test_signature_validation_roundtrip():
    token = "abc123token"
    gateway = TwilioGateway(
        Config(twilio_auth_token=token, public_base_url="https://bot.example.com")
    )
    url = "https://bot.example.com/whatsapp"
    params = {"From": "whatsapp:+1", "Body": "hi"}
    signature = RequestValidator(token).compute_signature(url, params)

    request = _FakeRequest(
        url="http://internal/whatsapp", path="/whatsapp", form=params, signature=signature
    )
    assert gateway.is_valid_signature(request) is True

    request.headers["X-Twilio-Signature"] = "tampered"
    assert gateway.is_valid_signature(request) is False


def test_signatures_not_enforced_without_token():
    gateway = TwilioGateway(Config())
    assert gateway.enforces_signatures is False
    assert gateway.is_valid_signature(_FakeRequest()) is False


def test_download_media_enforces_size_limit(monkeypatch):
    gateway = TwilioGateway(Config(max_audio_bytes=10))
    monkeypatch.setattr(
        "app.twilio_gateway.requests.get",
        lambda *a, **k: _FakeResponse([b"x" * 4, b"y" * 20]),
    )
    with pytest.raises(MediaTooLargeError):
        gateway.download_media("https://media", "audio/ogg")


def test_download_media_writes_file(monkeypatch, tmp_path):
    gateway = TwilioGateway(Config(max_audio_bytes=1000))
    monkeypatch.setattr(
        "app.twilio_gateway.requests.get",
        lambda *a, **k: _FakeResponse([b"hello", b"world"]),
    )
    media = gateway.download_media("https://media", "audio/ogg")
    try:
        assert media.content_type == "audio/ogg"
        assert media.path.endswith(".ogg")
        with open(media.path, "rb") as fh:
            assert fh.read() == b"helloworld"
    finally:
        os.remove(media.path)


# -- fakes -------------------------------------------------------------------


class _FakeRequest:
    def __init__(self, url="http://x/whatsapp", path="/whatsapp", form=None, signature=""):
        self.url = url
        self.path = path
        self.query_string = b""
        self.form = form or {}
        self.headers = {"X-Twilio-Signature": signature}


class _FakeResponse:
    def __init__(self, chunks):
        self._chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=8192):  # noqa: ARG002
        return iter(self._chunks)
