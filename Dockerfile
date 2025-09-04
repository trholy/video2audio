# Stage 1: Build
FROM python:3.12-slim AS builder

WORKDIR /app

COPY . /app

RUN pip install --prefix=/install --no-cache-dir .

# Install FFmpeg in builder
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Stage 2: Final runtime
FROM python:3.12-slim

WORKDIR /app

# Copy only the installed Python packages
COPY --from=builder /install /usr/local

# Copy app source
COPY src/video2audio /app/video2audio

# FFmpeg runtime (if needed)
COPY --from=builder /usr/bin/ffmpeg /usr/bin/ffmpeg
COPY --from=builder /usr/bin/ffprobe /usr/bin/ffprobe

ENV FLASK_APP=video2audio.app
CMD ["flask", "run", "--host=0.0.0.0"]