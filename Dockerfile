# Use official Playwright image with Python
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium && \
    playwright install-deps chromium

# Copy entire application
COPY . .

# SYNTAX CHECK - will fail build if any Python file has syntax errors
RUN python -m py_compile app.py && \
    find backend -name "*.py" -exec python -m py_compile {} \; && \
    find auth -name "*.py" -exec python -m py_compile {} \;

# Create necessary directories and files
RUN mkdir -p data/temp data/links data/results data/linkedin auth && \
    test -f auth/users.json || echo '[]' > auth/users.json && \
    chmod -R 777 data auth

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
    --timeout 600 \
    --access-logfile - \
    --error-logfile - \
    app:app
