FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    FLASK_APP=video2audio.app \
    FLASK_RUN_HOST=0.0.0.0 \
    FLASK_RUN_PORT=5000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN pip install --no-cache-dir .

EXPOSE 5000

CMD ["flask", "run"]
