"""Gunicorn configuration.

Whisper is CPU- and memory-heavy, and each worker is a separate process that
loads its own copy of the model. So we deliberately keep the worker count low
(default 2) rather than the usual ``2*cpu+1`` — more workers just multiply RAM.
Transcription is also slow, so the request timeout is generous, and workers are
recycled periodically to bound memory growth.

Override any of these via environment variables.
"""

import os

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))

# Recycle workers to counter any slow memory growth from long-lived models.
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "200"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "50"))

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
