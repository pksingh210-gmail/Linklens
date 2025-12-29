# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for Playwright and other packages
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    libu2f-udev \
    libvulkan1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies (including Gunicorn)
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium only for lighter image)
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application code (this will include auth/, backend/, static/, templates/)
COPY . .

# Create necessary data directories with proper permissions
RUN mkdir -p data/temp data/links data/results data/linkedin && \
    chmod -R 755 data

# Set environment variables
ENV FLASK_APP=app.py \
    PYTHONUNBUFFERED=1 \
    PORT=5000

# Expose port (will be overridden by cloud platform if needed)
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/login', timeout=5)"

# Start command - use PORT environment variable
CMD gunicorn --bind 0.0.0.0:${PORT} \
    --workers 3 \
    --threads 8 \
    --timeout 600 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --access-logfile - \
    --error-logfile - \
    app:app
