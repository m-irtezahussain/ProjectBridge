FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy
WORKDIR /workspace

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

FROM base AS development
RUN uv sync --frozen
EXPOSE 8000
CMD ["uv", "run", "fastapi", "dev", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS ocr-worker
RUN apt-get update \
    && apt-get install --no-install-recommends -y libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && uv sync --frozen --extra ocr --no-dev \
    && addgroup --system app \
    && adduser --system --ingroup app --home /home/app app \
    && chown -R app:app /workspace /home/app
USER app
CMD ["/workspace/.venv/bin/python", "-m", "app.workers.ingestion"]

FROM base AS production
RUN addgroup --system app && adduser --system --ingroup app app \
    && chown -R app:app /workspace
USER app
EXPOSE 8000
CMD ["uv", "run", "fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]

