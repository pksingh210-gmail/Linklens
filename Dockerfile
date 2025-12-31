# Use official Playwright image with Python
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    fonts-liberation \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium && \
    playwright install-deps chromium

# Copy entire application
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p data/temp data/links data/results data/linkedin auth && \
    test -f auth/users.json || echo '[]' > auth/users.json && \
    chmod -R 777 data auth

# Syntax check (will fail build if Python files have errors)
RUN python -m py_compile app.py && \
    python -m py_compile backend/linkedin_login.py && \
    python -m py_compile backend/linkedin_search.py && \
    python -m py_compile backend/linkedin_html.py && \
    python -m py_compile backend/linkedin_data_extract.py && \
    python -m py_compile backend/linkedin_contact_info.py

# Set environment variables
ENV FLASK_APP=app.py \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Expose port
EXPOSE 5000

# Start command
CMD gunicorn --bind 0.0.0.0:${PORT} \
    --workers 1 \
    --threads 2 \
    --timeout 1800 \
    --graceful-timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    app:app
