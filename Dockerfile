FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including curl for health checks
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (for E2E tests)
RUN playwright install --with-deps chromium

# Copy application code
COPY src/ ./src/
COPY tests/ ./tests/
COPY pytest.ini .

# Expose port
EXPOSE 8001

# Run the application with optimized settings for stability
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload", "--workers", "1", "--timeout-keep-alive", "65"]
