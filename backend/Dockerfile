# syntax=docker/dockerfile:1
# Multi-Stage: Dependencies in Builder, schlankes Runtime-Image
FROM python:3.11-slim AS builder

ARG BUILDKIT_INLINE_CACHE=1

WORKDIR /w
COPY requirements.txt .
# Retries + längeres Timeout für große Wheels (PyTorch); ohne --no-cache-dir: Pip-Cache in der Layer hilft bei erneutem Build
RUN pip install \
    --user \
    --retries 5 \
    --default-timeout 100 \
    -r requirements.txt

FROM python:3.11-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl socat gosu \
  && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

COPY --from=builder /root/.local /home/appuser/.local

ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Interner Flask-Port (127.0.0.1); öffentlich im Container ist BACKEND_EXPOSE_PORT (socat)
ENV BACKEND_INTERNAL_PORT=5002
ENV BACKEND_EXPOSE_PORT=5001

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

COPY --chown=appuser:appuser . .

EXPOSE 5001

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=120s \
  CMD curl -fsS http://127.0.0.1:5001/api/health || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
