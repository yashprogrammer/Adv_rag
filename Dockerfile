# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

# ---- deps layer (cache-friendly: only rebuilds when pyproject.toml changes) ----
FROM base AS deps
WORKDIR /app
COPY pyproject.toml ./

RUN uv pip install --system --no-cache \
        torch torchvision \
        --extra-index-url https://download.pytorch.org/whl/cpu

RUN uv pip install --system --no-cache -e .

# ---- app layer ----
FROM base AS app
WORKDIR /app

COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

COPY app/ ./app/
COPY scripts/ ./scripts/
COPY seed/ ./seed/

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000
CMD ["python", "scripts/serve.py"]
