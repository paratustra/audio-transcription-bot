import logging
import os
import tempfile
from typing import Optional

import requests
import whisper
from dotenv import load_dotenv
from flask import Flask, Response, request
import threading
from twilio.request_validator import RequestValidator
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("FROM", "")
WHISPER_MODEL_NAME = os.getenv("MODEL_NAME", "small")
PORT = int(os.getenv("PORT", "5000"))
DEBUG_MODE = os.getenv("DEBUG", "false").lower() in {"1", "true", "yes"}
ASYNC_REPLY = os.getenv("ASYNC_REPLY", "false").lower() in {"1", "true", "yes"}

logger = logging.getLogger("audio-transcription-bot")
logging.basicConfig(level=logging.DEBUG if DEBUG_MODE else logging.INFO)

if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
    logger.warning("Twilio credentials are not fully configured. Inbound validation and outbound messages may fail.")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN else None
twilio_validator = RequestValidator(TWILIO_AUTH_TOKEN) if TWILIO_AUTH_TOKEN else None

app = Flask(__name__)

logger.info("Loading Whisper model '%s'...", WHISPER_MODEL_NAME)
whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
logger.info("Whisper model loaded")


def fetch_media_to_tempfile(media_url: str) -> str:
    auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN else None
    with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as tmp_file:
        with requests.get(media_url, stream=True, timeout=60, auth=auth) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    tmp_file.write(chunk)
        return tmp_file.name


def transcribe_audio_file(file_path: str) -> str:
    result = whisper_model.transcribe(file_path)
    return result.get("text", "")


def is_audio_content_type(content_type: Optional[str]) -> bool:
    if not content_type:
        return False
    return content_type.lower().startswith("audio/")


def create_help_message() -> str:
    return (
        "Send a WhatsApp voice note or audio file and I'll transcribe it. "
        "Supported: audio/* (e.g. OGG/Opus voice notes)."
    )


def send_outbound_message(to_e164: str, body: str) -> None:
    if not twilio_client or not TWILIO_FROM_NUMBER:
        logger.error("Twilio client or FROM number not configured; cannot send outbound message")
        return
    from_whatsapp = TWILIO_FROM_NUMBER
    if not from_whatsapp.startswith("whatsapp:"):
        from_whatsapp = f"whatsapp:{from_whatsapp}"
    twilio_client.messages.create(body=body, from_=from_whatsapp, to=to_e164)


@app.get("/")
@app.get("/healthz")
def health() -> tuple[str, int]:
    return "ok", 200


@app.post("/whatsapp")
def whatsapp() -> Response:
    if twilio_validator:
        signature = request.headers.get("X-Twilio-Signature", "")
        url = request.url
        form = {k: v for k, v in request.form.items()}
        if not twilio_validator.validate(url, form, signature):
            logger.warning("Invalid Twilio signature")
            return Response("Invalid signature", status=403)

    from_number = request.form.get("From", "")
    num_media = int(request.form.get("NumMedia", "0") or 0)
    content_type = request.form.get("MediaContentType0") if num_media > 0 else None
    media_url = request.form.get("MediaUrl0") if num_media > 0 else None

    messaging_response = MessagingResponse()

    if num_media == 0:
        messaging_response.message(create_help_message())
        return Response(str(messaging_response), mimetype="application/xml")

    if not is_audio_content_type(content_type):
        messaging_response.message("Please send an audio message. Received media is not recognized as audio.")
        return Response(str(messaging_response), mimetype="application/xml")

    try:
        temp_path = fetch_media_to_tempfile(media_url) if media_url else None
        if not temp_path:
            raise RuntimeError("Failed to download media")

        if ASYNC_REPLY and from_number:
            messaging_response.message("Processing your audio. I will reply with the transcription shortly.")

            def _process_and_send() -> None:
                try:
                    transcription_text = transcribe_audio_file(temp_path).strip() or "(no transcription)"
                    send_outbound_message(to_e164=from_number, body=transcription_text)
                except Exception as thread_exc:
                    logger.exception("Background processing failed: %s", thread_exc)
                finally:
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass

            threading.Thread(target=_process_and_send, daemon=True).start()
            return Response(str(messaging_response), mimetype="application/xml")
        else:
            try:
                transcription = transcribe_audio_file(temp_path).strip() or "(no transcription)"
            finally:
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            messaging_response.message(transcription)
            return Response(str(messaging_response), mimetype="application/xml")
    except Exception as exc:
        logger.exception("Failed to process media: %s", exc)
        messaging_response.message("Sorry, there was an error processing your audio.")
        return Response(str(messaging_response), mimetype="application/xml", status=500)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG_MODE)
