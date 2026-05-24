# syntax=docker/dockerfile:1.4
FROM python:3.11-slim

WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

COPY . .

RUN mkdir -p /logs

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
