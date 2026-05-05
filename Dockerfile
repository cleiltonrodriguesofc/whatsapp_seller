# Stage 1: Build stage
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Stage 2: Runtime stage
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
# Ensure the virtualenv is used by default
ENV PATH="/opt/venv/bin:$PATH"
# Centralize Playwright browsers
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Install runtime library for PostgreSQL and system utils
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv

# Create a non-root user
RUN useradd --create-home appuser

# Install Playwright Chromium and its OS dependencies
# This is done as root so it has permissions to install system packages
RUN playwright install chromium && \
    playwright install-deps chromium && \
    # Ensure appuser owns the browsers and the app directory
    mkdir -p /ms-playwright && \
    chown -R appuser:appuser /ms-playwright /app

USER appuser

# Copy application source code
COPY --chown=appuser:appuser . .

# Default command for production (Render sets PORT env var)
CMD ["sh", "-c", "uvicorn core.presentation.web.app:app --host 0.0.0.0 --port ${PORT:-10000}"]
