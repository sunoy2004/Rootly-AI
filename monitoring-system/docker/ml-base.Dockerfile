# syntax=docker/dockerfile:1.4
# Shared ML layer: torch, sentence-transformers, faiss, sklearn (~1–2 GB).
# Rebuild only when docker/ml-base-requirements.txt changes.
FROM python:3.11-slim

WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/root/.cache/huggingface

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY docker/ml-base-requirements.txt /tmp/ml-base-requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=1000 -r /tmp/ml-base-requirements.txt

# Bake the embedding model into the image (layer cached until requirements change).
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
