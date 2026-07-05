from app import Config, create_app
from tests.fakes import FakeGateway


def _audio_form():
    return {
        "From": "whatsapp:+14150000000",
        "NumMedia": "1",
        "MediaContentType0": "audio/ogg",
        "MediaUrl0": "https://api.twilio.com/media/ME123",
    }


def test_no_media_returns_help(client):
    resp = client.post("/whatsapp", data={"From": "whatsapp:+1", "NumMedia": "0"})
    assert resp.status_code == 200
    assert b"transcribe" in resp.data.lower()


def test_non_audio_media_is_rejected(client):
    resp = client.post(
        "/whatsapp",
        data={
            "From": "whatsapp:+1",
            "NumMedia": "1",
            "MediaContentType0": "image/jpeg",
            "MediaUrl0": "https://api.twilio.com/media/ME1",
        },
    )
    assert resp.status_code == 200
    assert b"audio" in resp.data.lower()


def test_sync_transcription(client, transcriber, gateway):
    resp = client.post("/whatsapp", data=_audio_form())
    assert resp.status_code == 200
    assert b"hello world" in resp.data
    assert len(transcriber.calls) == 1
    assert len(gateway.downloaded) == 1
    assert gateway.sent == []  # sync mode replies inline, no REST push


def test_media_too_large(config, transcriber):
    gw = FakeGateway(too_large=True)
    app = create_app(config, transcriber=transcriber, gateway=gw)
    resp = app.test_client().post("/whatsapp", data=_audio_form())
    assert resp.status_code == 200
    assert b"too large" in resp.data.lower()
    assert transcriber.calls == []  # never got to transcription
    app.extensions["bot"].shutdown()


def test_async_reply(transcriber):
    cfg = Config(
        twilio_account_sid="AC1",
        twilio_auth_token="tok",
        twilio_whatsapp_from="whatsapp:+14155238886",
        async_reply=True,
        trusted_proxies=0,
    )
    gw = FakeGateway()
    app = create_app(cfg, transcriber=transcriber, gateway=gw)
    resp = app.test_client().post("/whatsapp", data=_audio_form())
    assert resp.status_code == 200
    assert b"shortly" in resp.data.lower()

    # Flush the single background worker, then assert the REST push happened.
    app.extensions["bot"].executor.shutdown(wait=True)
    assert gw.sent == [("whatsapp:+14150000000", "hello world")]


def test_transcription_error_still_replies_200(config, gateway):
    # A non-2xx status makes Twilio drop the TwiML, so the user would hear
    # nothing. Errors must come back as 200 with an apology in the body.
    class Boom:
        def transcribe(self, path):
            raise RuntimeError("kaboom")

    app = create_app(config, transcriber=Boom(), gateway=gateway)
    resp = app.test_client().post("/whatsapp", data=_audio_form())
    assert resp.status_code == 200
    assert b"error transcribing" in resp.data.lower()
    app.extensions["bot"].shutdown()


def test_invalid_signature_returns_403(transcriber):
    cfg = Config(twilio_auth_token="tok", trusted_proxies=0)
    gw = FakeGateway(enforce=True)
    gw.valid = False
    app = create_app(cfg, transcriber=transcriber, gateway=gw)
    resp = app.test_client().post("/whatsapp", data=_audio_form())
    assert resp.status_code == 403
    app.extensions["bot"].shutdown()
