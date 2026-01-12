FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    git \
    portaudio19-dev \
    libportaudio2 \
    && rm -rf /var/lib/apt/lists/*

# Copy project root requirements (contains all dependencies)
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Ensure FastAPI, Uvicorn & Database drivers are present
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    sse-starlette \
    python-multipart \
    psycopg2-binary \
    redis \
    flask-limiter \
    argon2-cffi

# Copy entire project to /app
COPY . /app/

# Expose port
EXPOSE 8000

# Run with uvicorn (trust reverse-proxy headers for correct scheme/host)
CMD ["uvicorn", "netapi.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--log-level", "info", "--proxy-headers", "--forwarded-allow-ips=*"]
