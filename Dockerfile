# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for Playwright Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    libxshmfence1 \
    libx11-6 \
    libxcb1 \
    libxext6 \
    libglib2.0-0 \
    wget \
    ca-certificates \
    fonts-liberation \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers using Python module syntax
RUN python -m playwright install --with-deps chromium

# Copy application code
COPY . .

# Create necessary data directories with proper permissions
RUN mkdir -p data/temp data/links data/results data/linkedin && \
    chmod -R 755 data

# Set environment variables
ENV FLASK_APP=app.py \
    PYTHONUNBUFFERED=1 \
    PORT=5000

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/login', timeout=5)" || exit 1

# Start command
CMD gunicorn --bind 0.0.0.0:${PORT} \
    --workers 3 \
    --threads 8 \
    --timeout 600 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --access-logfile - \
    --error-logfile - \
    app:app
