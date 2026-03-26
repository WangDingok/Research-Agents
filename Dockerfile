FROM python:3.11-slim

WORKDIR /app

# Install system deps for playwright and general build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml ./

# Install dependencies
RUN uv pip install --system -e "." && \
    uv pip install --system chainlit

# Install playwright browsers (needed for TikTok tools)
RUN playwright install --with-deps chromium || true

# Copy application code
COPY . .

# Create output directories
RUN mkdir -p public/charts output/etsy_data research_agent/output/etsy_data

EXPOSE 8080

CMD ["chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "8080"]
