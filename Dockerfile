# -----------------------------------------------------
# STAGE 1: BUILDER (Creates the virtual environment)
# -----------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /app

# 1. Install uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Optimization Flags for uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Copy dependency files first to leverage Docker caching
COPY pyproject.toml uv.lock* ./

# Use uv sync to install dependencies into an isolated Virtual Environment (.venv)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copy the rest of the application code and all entrypoint scripts
COPY . .

# Install the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# -----------------------------------------------------
# STAGE 2: RUNTIME (Production-ready image)
# -----------------------------------------------------
FROM python:3.12-slim

# Install system dependencies (e.g., PostgreSQL client libraries)
# Uncomment the line below if you use psycopg2 (NOT psycopg2-binary)
# RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev \
#     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy uv binary from builder
COPY --from=builder /bin/uv /bin/uv

# Copy the Virtual Environment and code from the builder stage
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/. /app/

# Set Environment Variables
# PATH: Add the venv's bin directory for clean execution (e.g., calling 'python' and 'gunicorn')
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE="core.settings"


# RUN apt-get update && apt-get install -y dos2unix

# # Fix the line endings and make executable
# RUN dos2unix /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Make entrypoint scripts executable
RUN chmod +x /app/entrypoint.sh /app/entrypoint-k8s.sh

# Default ENTRYPOINT for Kubernetes deployment (Uses the script tailored for K8s)
ENTRYPOINT [ "/app/entrypoint.sh"]

# Default CMD (Used if no custom command is passed, but entrypoint-k8s.sh takes over)
CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000"]