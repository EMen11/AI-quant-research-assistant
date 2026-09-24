# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:0.12.17 AS uv

FROM python:3.12.11-slim AS uv-prod

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM uv-prod AS test

COPY alembic.ini ./
COPY migrations ./migrations
COPY app.py ./
COPY docs ./docs
COPY reports ./reports
COPY tests ./tests
RUN uv sync --frozen --all-groups --no-editable
ENV PATH="/app/.venv/bin:${PATH}"
CMD ["pytest", "-q"]

FROM python:3.12.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

RUN groupadd --system app && useradd --system --gid app --home-dir /app app
WORKDIR /app
COPY --from=uv-prod --chown=app:app /app/.venv ./.venv
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app app.py ./
COPY --chown=app:app docs ./docs
COPY --chown=app:app reports ./reports

USER app
STOPSIGNAL SIGTERM

CMD ["uvicorn", "ai_quant.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
