### Audio Transcription WhatsApp Bot

Flask service that receives WhatsApp audio messages via Twilio and replies with a transcription using OpenAI Whisper.

### Why

WhatsApp voice notes are slow to skim. This bot turns them into text.

### Features

- Loads Whisper model once at startup
- Validates Twilio signatures
- Supports WhatsApp voice notes (OGG/Opus) and general `audio/*`
- Sync or async replies via env flag
- Health endpoint at `/healthz`

### Requirements

- Python 3.10+
- ffmpeg installed on system path
- Twilio WhatsApp Sandbox or Business API

### Install

```bash
pip install -r requirements.txt
```

Install ffmpeg if you don't have it:

```bash
brew install ffmpeg
```

### Configure

Create a `.env` file:

```bash
ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AUTH_TOKEN=your_auth_token
FROM=whatsapp:+1415xxxxxxx
MODEL_NAME=small
PORT=5000
DEBUG=false
ASYNC_REPLY=false
```

Alternatively, copy and edit `env.sample` to `.env`.

Notes:
- `FROM` can be configured with or without the `whatsapp:` prefix; the app handles both.
- `MODEL_NAME` options: `tiny`, `base`, `small`, `medium`, `large` (trade speed vs accuracy).
- `ASYNC_REPLY=true` returns immediately and sends the transcription in a second message.

### Run

```bash
python main.py
```

Expose locally for Twilio callbacks:

```bash
ngrok http 5000
```

Set your Twilio WhatsApp sandbox Inbound Webhook URL to:

```
POST https://<your-ngrok-domain>/whatsapp
```

### Usage

- Send a voice note or audio file to your Twilio WhatsApp number
- You will receive the transcription back

### Notes on Cost

Each audio incurs costs for messaging and compute. Whisper model size affects speed and cost; smaller models are faster and cheaper to run.