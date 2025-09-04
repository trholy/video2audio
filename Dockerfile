# Use a small, official Python slim image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    FLASK_APP=video2audio.app \
    FLASK_RUN_HOST=0.0.0.0 \
    FLASK_RUN_PORT=5000

# Set working directory
WORKDIR /app

# Install system dependencies (FFmpeg, build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire project
COPY . /app

# Install your package in editable mode
RUN pip install --no-cache-dir .

# Expose Flask port
EXPOSE 5000

# Default command to run the web app
CMD ["flask", "run"]
