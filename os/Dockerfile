# KI-ana OS - Docker Container
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    portaudio19-dev \
    espeak \
    libespeak-dev \
    ffmpeg \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Ollama (optional - for LLM support)
RUN curl -fsSL https://ollama.ai/install.sh | sh || true

# Copy application
COPY . .

# Create data directories
RUN mkdir -p /root/.kiana /root/.kiana/plugins /root/.kiana_sync

# Expose ports
EXPOSE 8090

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV KIANA_ENV=production

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8090/health || exit 1

# Start command (REST API by default)
CMD ["python3", "start_api.py"]
