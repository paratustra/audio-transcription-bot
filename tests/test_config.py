from app.config import DEFAULT_MAX_AUDIO_BYTES, Config


def test_defaults_from_empty_env():
    cfg = Config.from_env({})
    assert cfg.whisper_model == "small"
    assert cfg.whisper_language is None
    assert cfg.async_reply is False
    assert cfg.port == 5000
    assert cfg.max_audio_bytes == DEFAULT_MAX_AUDIO_BYTES
    assert cfg.twilio_configured is False
    assert cfg.can_send_outbound is False


def test_parses_env():
    cfg = Config.from_env(
        {
            "TWILIO_ACCOUNT_SID": "AC123",
            "TWILIO_AUTH_TOKEN": "secret",
            "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886",
            "WHISPER_MODEL": "medium",
            "WHISPER_LANGUAGE": "es",
            "ASYNC_REPLY": "true",
            "PORT": "9000",
            "MAX_AUDIO_BYTES": "1024",
        }
    )
    assert cfg.twilio_configured is True
    assert cfg.can_send_outbound is True
    assert cfg.whisper_model == "medium"
    assert cfg.whisper_language == "es"
    assert cfg.async_reply is True
    assert cfg.port == 9000
    assert cfg.max_audio_bytes == 1024


def test_bad_ints_fall_back_to_defaults():
    cfg = Config.from_env({"PORT": "not-a-number", "MAX_AUDIO_BYTES": ""})
    assert cfg.port == 5000
    assert cfg.max_audio_bytes == DEFAULT_MAX_AUDIO_BYTES


def test_blank_language_is_none():
    assert Config.from_env({"WHISPER_LANGUAGE": ""}).whisper_language is None
