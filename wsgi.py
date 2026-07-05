"""WSGI entrypoint.

Production:  gunicorn wsgi:app -c gunicorn.conf.py
Development: python wsgi.py   (or: flask --app wsgi run --debug)
"""

from __future__ import annotations

from app import create_app

app = create_app()

if __name__ == "__main__":
    config = app.config["BOT_CONFIG"]
    app.run(host="127.0.0.1", port=config.port, debug=config.debug)
