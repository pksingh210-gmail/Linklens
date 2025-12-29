# Use official Playwright image with Python
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire application
COPY . .

# Create necessary data directories
RUN mkdir -p data/temp data/links data/results data/linkedin && \
    chmod -R 755 data

# Set environment variables
ENV FLASK_APP=app.py \
    PYTHONUNBUFFERED=1 \
    PORT=5000

# Expose port
EXPOSE 5000

# Start command
CMD gunicorn --bind 0.0.0.0:${PORT} \
    --workers 3 \
    --threads 8 \
    --timeout 600 \
    --access-logfile - \
    --error-logfile - \
    app:app
