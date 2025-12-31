# Use official Playwright image with Python
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium required for your scraper)
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy entire application
COPY . .

# Create necessary data directories with proper permissions
RUN mkdir -p data/temp data/links data/results data/linkedin auth && \
    chmod -R 777 data auth

# Create empty auth/users.json if it doesn't exist
RUN echo '[]' > auth/users.json && chmod 666 auth/users.json

# Set environment variables
ENV FLASK_APP=app.py \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    HOME=/app

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT}/ || exit 1

# Start command - CRITICAL: Use 0.0.0.0 not 127.0.0.1
CMD gunicorn --bind 0.0.0.0:${PORT} \
    --workers 1 \
    --threads 4 \
    --timeout 1200 \
    --worker-class sync \
    --worker-tmp-dir /dev/shm \
    --access-logfile - \
    --error-logfile - \
    --log-level debug \
    --preload \
    app:app
