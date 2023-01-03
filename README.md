# Audio Transcription WhatsApp Bot

A simple Flask application that allows users to send audio messages through WhatsApp and receive the transcribed text as a response, using OpenAI’s Whisper.

## Prerequisites

- Python 3.6 or higher
- [Whisper](https://github.com/openai/whisper)
- Flask
- [Twilio](https://www.twilio.com/) account and WhatsApp API sandbox
- [ngrok](https://ngrok.com/)

## Setup

1. Clone this repository and navigate to the project directory.
2. Install the required packages using pip:

`pip install -r requirements.txt`

3. Set up a [Twilio account](https://www.twilio.com/) and WhatsApp API sandbox.
4. Create a file named .env in the root of the project directory and set the following environment variables:

```yaml
ACCOUNT_SID=YOUR_TWILIO_ACCOUNT_SID
AUTH_TOKEN=YOUR_TWILIO_AUTH_TOKEN
FROM=YOUR_TWILIO_PHONE_NUMBER
```

5. Run the application
6. Expose the application using [ngrok](https://ngrok.com/):

`ngrok http 5000`

7. Make sure to follow the instructions in the [Twilio documentation](https://www.twilio.com/docs/whatsapp/quickstart/python) to set up your sandbox phone number and configure the webhook for incoming messages.

## Usage

1. Send an audio message to the configured sandbox phone number through WhatsApp.
2. The application will transcribe the audio and send the transcribed text back as a response.