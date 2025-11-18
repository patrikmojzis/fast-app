FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

ARG APP_UID=999
ARG APP_GID=999
RUN groupadd -g "$APP_GID" -r appuser \
 && useradd  -u "$APP_UID" -g "$APP_GID" -m -r appuser

RUN mkdir -p /app/log /app/storage

COPY --chown=appuser:appuser requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

COPY --chown=appuser:appuser . /app

RUN chmod +x /app/scripts/*.sh || true

USER appuser
ENV PYTHONPATH=/app