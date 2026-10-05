FROM python:3.11-slim

# Install system dependencies & ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app/ ./app/
COPY static/ ./static/
COPY run.py .

# Environment variables & memory optimization
ENV PORT=8000
ENV HOST=0.0.0.0
ENV DOCKER=1
ENV DOWNLOAD_DIR=/app/downloads
ENV AUTO_CLEANUP_HOURS=2
ENV MALLOC_ARENA_MAX=2
ENV PYTHONUNBUFFERED=1

# Create downloads volume directory
RUN mkdir -p /app/downloads /app/bin

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --limit-concurrency 25"]
