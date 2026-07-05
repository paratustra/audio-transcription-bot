# Audio Transcription WhatsApp Bot

[![CI](https://github.com/paratustra/audio-transcription-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/paratustra/audio-transcription-bot/actions/workflows/ci.yml)

A Flask service that receives WhatsApp voice notes through Twilio and replies
with a text transcription, using [OpenAI Whisper](https://github.com/openai/whisper).

WhatsApp voice notes are slow to skim. This bot turns them into text you can read.

## How it works

```
WhatsApp user ──▶ Twilio ──▶ POST /whatsapp ──▶ validate signature
                                                      │
                                          download media (authenticated)
                                                      │
                                              Whisper transcribe
                                                      │
                              ┌───────────────────────┴───────────────────┐
                         sync reply (TwiML)                     async: ack now, then
                         in the same response                   send result via REST API
```

- **Sync mode** (default): transcribe inline and return the text in the webhook
  response. Simple, but the webhook is held open while Whisper runs — fine for
  short clips and small models.
- **Async mode** (`ASYNC_REPLY=true`): acknowledge immediately, transcribe on a
  background worker, and deliver the result as a second WhatsApp message via the
  Twilio REST API. Recommended for larger models or longer audio.

## Project layout

```
app/
  __init__.py        create_app() application factory (dependency-injected)
  config.py          immutable Config loaded from the environment
  transcription.py   lazy, lock-serialized Whisper wrapper
  twilio_gateway.py  signature validation, media download, outbound sending
  webhook.py         /whatsapp and /healthz routes (blueprint)
  services.py        collaborator container held on app.extensions
wsgi.py              entrypoint for gunicorn and the dev server
gunicorn.conf.py     production process configuration
tests/               pytest suite (mocks Whisper + Twilio, no ML stack needed)
```

## Requirements

- Python 3.10+
- **ffmpeg** on the system path — Whisper shells out to it to decode audio
  (WhatsApp voice notes arrive as OGG/Opus)
- A Twilio account with the WhatsApp Sandbox or the WhatsApp Business API

## Setup

```bash
# 1. Install ffmpeg (macOS; use apt/your package manager on Linux)
brew install ffmpeg

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Configure
cp .env.example .env   # then edit .env
```

### Configuration

All settings come from environment variables (loaded from `.env` in
development). See [`.env.example`](.env.example) for the full list.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `TWILIO_ACCOUNT_SID` | yes | – | Twilio Account SID (`AC…`). |
| `TWILIO_AUTH_TOKEN` | yes | – | Twilio auth token. Also enables signature validation. |
| `TWILIO_WHATSAPP_FROM` | yes | – | Your WhatsApp sender, e.g. `whatsapp:+14155238886` (prefix optional). |
| `WHISPER_MODEL` | no | `small` | `tiny` \| `base` \| `small` \| `medium` \| `large`. |
| `WHISPER_LANGUAGE` | no | auto | Force a language (e.g. `es`); blank auto-detects. |
| `PUBLIC_BASE_URL` | no | – | Public HTTPS base URL for reliable signature validation behind a proxy. |
| `TRUSTED_PROXIES` | no | `1` | Proxies to trust for `X-Forwarded-*` (ProxyFix). `0` disables. |
| `ASYNC_REPLY` | no | `false` | Ack immediately and reply in a second message. |
| `MAX_AUDIO_BYTES` | no | `26214400` | Reject media larger than this (25 MB). |
| `DOWNLOAD_TIMEOUT` | no | `60` | Media download timeout in seconds. |
| `DEBUG` | no | `false` | Flask debug mode (dev only). |
| `PORT` | no | `5000` | Dev server port. |

## Run

### Development

```bash
python wsgi.py
```

Expose it to Twilio with a tunnel:

```bash
ngrok http 5000
```

Set your Twilio WhatsApp Sandbox **"When a message comes in"** webhook to:

```
POST https://<your-ngrok-domain>/whatsapp
```

> **Signature validation behind ngrok/proxies.** Twilio signs the exact HTTPS
> URL it calls, but a tunnel terminates TLS and your app sees plain HTTP — the
> mismatch makes validation fail. This app corrects it two ways: `ProxyFix`
> honors `X-Forwarded-Proto`/`Host` automatically, and you can pin the signed
> URL explicitly by setting `PUBLIC_BASE_URL=https://<your-ngrok-domain>`, which
> is the most robust option.

### Production

```bash
pip install -r requirements.txt
gunicorn wsgi:app -c gunicorn.conf.py
```

Whisper is CPU- and memory-heavy, and **each gunicorn worker loads its own copy
of the model**, so `gunicorn.conf.py` keeps the worker count low (default 2)
rather than the usual `2*cpu+1`. Tune it with env vars (`WEB_CONCURRENCY`,
`GUNICORN_TIMEOUT`, …). For heavier models, prefer `ASYNC_REPLY=true` so the
webhook returns quickly instead of blocking a worker for the whole transcription.

### Docker

```bash
docker build -t audio-transcription-bot .
docker run --rm -p 8000:8000 --env-file .env audio-transcription-bot
```

The image bundles ffmpeg and runs as a non-root user. Model weights download on
first use; mount a volume at `/home/appuser/.cache` to persist them across runs.

## Usage

Send a voice note or audio file to your Twilio WhatsApp number, and the bot
replies with the transcription. Send anything else and it replies with help.

## Development

```bash
pip install -r requirements-dev.txt

pytest              # run the test suite
ruff check .        # lint
ruff format .       # format
```

The suite substitutes fakes for Whisper and Twilio, so it runs in milliseconds
and needs neither the ML stack nor network access. CI runs lint, format check,
and tests on Python 3.10–3.12.

## Notes on cost & performance

- Each audio message incurs Twilio messaging costs plus compute for
  transcription. Smaller Whisper models are faster and cheaper.
- For faster, lower-memory CPU inference, consider swapping in
  [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper) (CTranslate2)
  behind the same `Transcriber` interface in `app/transcription.py`.

## Security

- Inbound requests are rejected unless they carry a valid `X-Twilio-Signature`
  (when `TWILIO_AUTH_TOKEN` is set). Always set it in production.
- Media is streamed to a temp file with a size cap (`MAX_AUDIO_BYTES`) and
  removed after transcription.
- Never commit `.env`; it is already gitignored.

## License

[MIT](LICENSE.md)
