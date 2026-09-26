FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY netease_sidecar ./netease_sidecar

CMD ["sh", "-c", "uv run --no-dev uvicorn netease_sidecar.app:app --host 0.0.0.0 --port ${PORT:-3101}"]
