# syntax=docker/dockerfile:1.4
# Lightweight Python service template (copy into service dirs or reference via build args).
# Build with: docker build -f docker/python-service.Dockerfile --build-arg SERVICE_PORT=8007 .
ARG SERVICE_PORT=8000
FROM python:3.11-slim

WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=1000 -r requirements.txt

COPY . .

EXPOSE ${SERVICE_PORT}
CMD uvicorn main:app --host 0.0.0.0 --port ${SERVICE_PORT}
