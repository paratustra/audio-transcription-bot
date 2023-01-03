import flask
from flask import request
import tempfile
import requests
import whisper
import os
from twilio.rest import Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get Twilio Account SID, Auth Token, and From phone number from environment variables
ACCOUNT_SID = os.environ.get("ACCOUNT_SID")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN")
FROM = os.environ.get("FROM")

client = Client(ACCOUNT_SID, AUTH_TOKEN)

app = flask.Flask(__name__)


def transcribe_audio(audio_url, model_name="base"):
    """Transcribe audio at the given URL using the specified model.

    Args:
        audio_url (str): URL of the audio to transcribe.
        model_name (str, optional): Name of the model to use for transcription. Defaults to "base".

    Returns:
        str: Transcribed text.
    """
    model = whisper.load_model(model_name)
    response = requests.get(audio_url)
    with tempfile.TemporaryDirectory() as temp_dir:
        audio_file_path = f"{temp_dir}/audio.tmp"
        with open(audio_file_path, "wb") as audio_file:
            audio_file.write(response.content)
        result = model.transcribe(audio_file_path)
    return result["text"]


def send_message(senderId, message):
    """Send a message to the specified phone number.

    Args:
        senderId (str): Phone number to send the message to.
        message (str): Message to send.

    Returns:
        twilio.rest.Message: Result of the message creation request.
    """
    res = client.messages.create(body=message, from_=FROM, to=f"whatsapp:+{senderId}")
    return res


@app.route("/")
@app.route("/home")
def home():
    return "Hello World"


@app.route("/whatsapp", methods=["GET", "POST"])
def whatsapp():
    """Endpoint for handling incoming WhatsApp messages."""

    senderId = request.form["From"].split("+")[1]
    mediaUrl = request.form["MediaUrl0"]

    try:
        response_message = transcribe_audio(mediaUrl)
        send_message(senderId=senderId, message=response_message)
    except Exception as e:
        print(e)
    return "200"


if __name__ == "__main__":
    app.run(port=5000, debug=True)
    # Remember to run ngrok to expose the local server to the internet
