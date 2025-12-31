FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install additional dependencies
RUN apt-get update && apt-get install -y \
    fonts-liberation \
    fonts-noto-color-emoji \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright with all dependencies
RUN playwright install chromium
RUN playwright install-deps chromium

COPY . .

# Create directories with proper permissions
RUN mkdir -p data/temp data/links data/results data/linkedin auth && \
    test -f auth/users.json || echo '[]' > auth/users.json && \
    chmod -R 777 data auth

# Syntax check
RUN python -m py_compile app.py

ENV FLASK_APP=app.py \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

EXPOSE 5000

CMD gunicorn --bind 0.0.0.0:${PORT} \
    --workers 1 \
    --threads 2 \
    --timeout 1800 \
    --graceful-timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    app:app
