"""Whisper transcription, wrapped for safe use inside a web server.

Two facts drive this design:

1. A loaded Whisper model is **not** thread-safe. ``model.transcribe`` mutates
   internal decoder state, so concurrent calls on one instance corrupt each
   other. We therefore guard every call with a lock, serializing transcription
   across all request threads.
2. Loading a model is slow and holds the weights in memory, so we load exactly
   once (lazily, on first use) and reuse the instance.

``whisper`` and ``torch`` are imported lazily inside ``_ensure_loaded`` so that
importing this module (e.g. in tests) does not pull in heavy ML dependencies.
"""

from __future__ import annotations

import logging
import threading
from typing import Protocol

logger = logging.getLogger(__name__)


class Transcriber(Protocol):
    """Minimal interface the webhook depends on (so tests can substitute it)."""

    def transcribe(self, audio_path: str) -> str: ...


class WhisperTranscriber:
    """Lazily-loaded, lock-serialized wrapper around an OpenAI Whisper model."""

    def __init__(self, model_name: str, language: str | None = None) -> None:
        self._model_name = model_name
        self._language = language
        self._model = None
        self._load_lock = threading.Lock()
        self._infer_lock = threading.Lock()
        self._use_fp16 = False

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:  # double-checked: another thread won
                return
            import torch  # noqa: PLC0415 -- deferred to keep import light
            import whisper  # noqa: PLC0415

            self._use_fp16 = torch.cuda.is_available()
            device = "cuda" if self._use_fp16 else "cpu"
            logger.info("Loading Whisper model %r on %s...", self._model_name, device)
            self._model = whisper.load_model(self._model_name, device=device)
            logger.info("Whisper model %r loaded", self._model_name)

    def transcribe(self, audio_path: str) -> str:
        self._ensure_loaded()
        assert self._model is not None
        # Serialize: the model is not safe for concurrent transcribe() calls.
        with self._infer_lock:
            result = self._model.transcribe(
                audio_path,
                language=self._language,
                fp16=self._use_fp16,  # avoids the noisy "FP16 unsupported on CPU" warning
            )
        return str(result.get("text", "")).strip()

    def warm_up(self) -> None:
        """Eagerly load the model (e.g. at gunicorn preload time)."""
        self._ensure_loaded()
