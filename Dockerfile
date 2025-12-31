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
RUN mkdir -p data/temp data/links data/results data/linkedin && \
    chmod -R 755 data

# Set environment variables
ENV FLASK_APP=app.py \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Expose port
EXPOSE 5000

# Start command with increased timeout for long-running scrapes
CMD gunicorn --bind 0.0.0.0:${PORT} \
    --workers 1 \
    --threads 4 \
    --timeout 1200 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    app:app
