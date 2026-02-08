FROM python:3.12-slim AS base

LABEL org.opencontainers.image.source="https://github.com/sirrele/sift"
LABEL org.opencontainers.image.description="Structured session capture & AI extraction CLI"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Install system dependencies for audio processing (optional)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (cached layer)
COPY pyproject.toml .
RUN pip install --no-cache-dir ".[all]"

# Copy application code
COPY . .
RUN pip install --no-cache-dir -e .

# Default data directory
ENV SIFT_HOME=/data
VOLUME /data

# Non-root user for security
RUN useradd --create-home sift
USER sift

ENTRYPOINT ["sift"]
CMD ["--help"]
