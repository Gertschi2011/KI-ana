# Multi-arch friendly base; use buildx to target linux/arm64 or linux/arm/v7 for Raspberry Pi
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    KI_ROOT=/root/ki_ana

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy minimal KI_ana subset needed for Sub-KI server
# Assuming we mount the full repo at runtime; keep image small by copying only required modules
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy runtime files
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# The Sub-KI server code path inside KI_ana project
# Expect the project to be mounted at /root/ki_ana
VOLUME ["/root/ki_ana"]
EXPOSE 5055

# Optional cron-like loop can be enabled via ENABLE_CRON=true
ENV ENABLE_CRON=false \
    CRON_INTERVAL_SECONDS=86400 \
    MOTHER_KI_URL=http://host.docker.internal:8000

ENTRYPOINT ["/app/entrypoint.sh"]
