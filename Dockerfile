# =========================
# Base images and versions
# =========================
ARG PYTHON_IMAGE=python:3.11.9-slim
ARG UV_VERSION=0.7.17

# =========================
# Stage 1: Builder
# - Creates a locked, reproducible venv using uv
# - Uses BuildKit cache mounts for faster incremental builds
# =========================
FROM ${PYTHON_IMAGE} AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps required to compile wheels and talk to Postgres (psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc build-essential libpq-dev curl ca-certificates git \
 && rm -rf /var/lib/apt/lists/*

# Install uv via pip (matches user's requested pattern)
RUN pip install --no-cache-dir "uv==${UV_VERSION}"

WORKDIR /app

# Copy dependency metadata first to maximize layer caching
COPY pyproject.toml ./pyproject.toml

# 1) Generate/refresh lock file (deterministic builds)
# 2) Pre-fetch deps to cache without installing the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv lock && \
    uv sync --locked --no-install-project

# Copy the rest of the project
COPY . .

# Create the final virtualenv including the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# (Optional) You can run smoke tests/linters here:
# RUN uv run pytest -q

# =========================
# Stage 2: Runtime
# - Thin runtime with only what is needed to run the app
# - Copies the built .venv and source from the builder layer
# =========================
FROM ${PYTHON_IMAGE} AS runtime

# Runtime OS deps (libpq for psycopg2, CA certs for outbound HTTPS)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

# Use non-root user for better security
RUN useradd -m -u 10001 appuser

WORKDIR /app

# Copy virtualenv and application code from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app /app

# Ensure the virtualenv is preferred
ENV PATH="/app/.venv/bin:${PATH}"

# -------------------------
# ENTRYPOINT options
# -------------------------
# Option A (recommended): run module directly via uv
# ENTRYPOINT ["uv", "run", "-m", "src.main"]

# Option B: if you defined a console script in pyproject like:
#   [project.scripts]
#   dqf = "src.main:main"
# then you can switch to:
ENTRYPOINT ["dqf"]

# -------------------------
# Notes:
# - Provide credentials via env (e.g., PG_CONN, BQ_CONN, GCHAT_DQ_WEBHOOK, DQ_EMAILS, SMTP_*)
# - Mount configs at /app/config in KubernetesPodOperator or docker run:
#     -v $PWD/config:/app/config
# - For Oracle 'oracledb' thin mode, no extra OS libs required; thick mode needs Instant Client.
# - Healthcheck is optional and depends on how you run the framework (CLI vs service).