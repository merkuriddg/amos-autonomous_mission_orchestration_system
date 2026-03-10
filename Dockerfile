# AMOS — Autonomous Mission Orchestration System
# Production container
FROM python:3.11-slim

LABEL maintainer="MavrixOne / Merkuri DDG"
LABEL description="AMOS — Autonomous Mission Orchestration System"

WORKDIR /opt/amos

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl net-tools && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY core/ ./core/
COPY services/ ./services/
COPY integrations/ ./integrations/
COPY simulator/ ./simulator/
COPY plugins/ ./plugins/
COPY web/ ./web/
COPY config/ ./config/
COPY db/ ./db/

ENV PYTHONUNBUFFERED=1

EXPOSE 2600

HEALTHCHECK --interval=30s --timeout=5s \
    CMD curl -f http://localhost:2600/login || exit 1

CMD ["python3", "web/app.py"]
