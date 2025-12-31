FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data/temp data/links data/results auth && \
    chmod -R 755 data auth && \
    echo '[]' > auth/users.json && chmod 644 auth/users.json

ENV FLASK_APP=app.py \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    HOME=/app

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD gunicorn --bind 0.0.0.0:${PORT} \
    --workers 1 \
    --threads 4 \
    --timeout 1200 \
    --worker-class sync \
    --worker-tmp-dir /dev/shm \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    app:app
