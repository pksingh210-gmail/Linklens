# Use official Playwright image with Python
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

RUN apt-get update && apt-get install -y \
    fonts-liberation \
    fonts-noto-color-emoji \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libxshmfence1 \
    libgtk-3-0 \
    libxss1 \
    lsb-release \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data/temp data/links data/results auth && \
    test -f auth/users.json || echo '[]' > auth/users.json && \
    chmod -R 777 data auth

RUN python -m py_compile app.py

ENV FLASK_APP=app.py \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

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

