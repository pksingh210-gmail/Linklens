FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install additional dependencies for anti-detection
RUN apt-get update && apt-get install -y \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libappindicator3-1 \
    libasound2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright with extra browser dependencies
RUN playwright install chromium
RUN playwright install-deps chromium

COPY . .

RUN mkdir -p data/temp data/links data/results data/linkedin auth && \
    test -f auth/users.json || echo '[]' > auth/users.json && \
    chmod -R 777 data auth

ENV FLASK_APP=app.py \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    # LinkedIn bot detection countermeasures
    DISPLAY=:99

EXPOSE 5000

CMD gunicorn --bind 0.0.0.0:${PORT} \
    --workers 1 \
    --threads 2 \
    --timeout 1200 \
    --access-logfile - \
    --error-logfile - \
    app:app
