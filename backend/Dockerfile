# ── Backend Dockerfile ──────────────────────────────────────────────────────
# Multi-stage build: builder installs deps with uv, runner copies the venv.
# No secrets or .env files are baked in — all configuration is via environment
# variables at container start (see .env.example).
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv==0.5.5

# Copy dependency manifest first for layer caching
COPY pyproject.toml uv.lock* ./

# Install all dependencies into /app/.venv
RUN uv sync --no-dev --frozen

# ── Stage 2: runner ───────────────────────────────────────────────────────────
FROM python:3.12-slim AS runner

WORKDIR /app

# Non-root user for least-privilege runtime
RUN useradd --create-home --shell /bin/bash nova

# Copy the virtualenv from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY backend/ ./backend/
COPY agents/ ./agents/
COPY rag/ ./rag/
COPY memory/ ./memory/
COPY integrations/ ./integrations/
COPY sample_data/ ./sample_data/

# Create data directory (SQLite writes here when DATABASE_URL is sqlite)
RUN mkdir -p /app/data && chown nova:nova /app/data

USER nova

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/backend"
ENV PYTHONIOENCODING="utf-8"
# Default to fake provider so the image is self-contained for demos;
# override via env vars for production.
ENV LLM_PROVIDER="fake"
ENV VECTOR_STORE="memory"
ENV GRAPH_STORE="memory"

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
