FROM python:3.11-slim

WORKDIR /app

# System deps: build tools for chromadb/pymupdf native wheels, curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# Copy the full application source
COPY . .

# Each service overrides this with its own `command:` in docker-compose.yml
CMD ["python", "-m", "dashboard.app"]
