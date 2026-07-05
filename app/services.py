"""Container wiring the app's collaborators together.

Held on ``app.extensions["bot"]`` so views can reach the transcriber, the
Twilio gateway, and a single-worker executor without importing globals. Tests
build this with fakes and hand it to :func:`create_app`.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .config import Config
from .transcription import Transcriber
from .twilio_gateway import TwilioGateway


@dataclass
class Services:
    config: Config
    transcriber: Transcriber
    gateway: TwilioGateway
    # One worker: transcription must be serialized anyway (the model is not
    # thread-safe), and this bounds background threads under load.
    executor: ThreadPoolExecutor

    def submit(self, fn: Callable[..., None], *args: object) -> None:
        self.executor.submit(fn, *args)

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
