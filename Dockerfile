FROM python:3.14-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ufw \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]"

# Copy application
COPY src/ ./src/

# Create data directory
RUN mkdir -p /app/data

# Default command
CMD ["python", "-m", "src.worker"]
