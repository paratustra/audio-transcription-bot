"""In-memory test doubles shared across the suite.

None of these import whisper, torch, or reach the network, so the suite runs
fast and without the heavy ML stack installed.
"""

from __future__ import annotations

import tempfile

from app.twilio_gateway import Media, MediaTooLargeError


class FakeTranscriber:
    """Records the paths it was asked to transcribe and returns canned text."""

    def __init__(self, text: str = "hello world") -> None:
        self.text = text
        self.calls: list[str] = []

    def transcribe(self, audio_path: str) -> str:
        self.calls.append(audio_path)
        return self.text


class FakeGateway:
    """In-memory stand-in for TwilioGateway — never touches the network."""

    def __init__(self, *, enforce: bool = False, too_large: bool = False) -> None:
        self.enforces_signatures = enforce
        self._too_large = too_large
        self.valid = True
        self.sent: list[tuple[str, str]] = []
        self.downloaded: list[str] = []

    def is_valid_signature(self, request) -> bool:  # noqa: ARG002
        return self.valid

    def download_media(self, media_url: str, content_type: str | None) -> Media:
        self.downloaded.append(media_url)
        if self._too_large:
            raise MediaTooLargeError("too large")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".ogg")  # noqa: SIM115
        tmp.write(b"audio")
        tmp.close()
        return Media(path=tmp.name, content_type=content_type)

    def send_whatsapp(self, to: str, body: str) -> bool:
        self.sent.append((to, body))
        return True
