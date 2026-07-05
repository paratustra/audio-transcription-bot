# Whisper decodes audio by shelling out to the ffmpeg binary, so it must be
# present in the image — pip alone is not enough.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user.
RUN useradd --create-home appuser \
    && chown -R appuser:appuser /app
USER appuser

# Whisper caches downloaded model weights here; give the app user a writable home.
ENV XDG_CACHE_HOME=/home/appuser/.cache

EXPOSE 8000

CMD ["gunicorn", "wsgi:app", "-c", "gunicorn.conf.py"]
