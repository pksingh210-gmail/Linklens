FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium
RUN playwright install-deps chromium

COPY . .

RUN mkdir -p data/temp data/links data/results data/linkedin auth && \
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
    --access-logfile - \
    --error-logfile - \
    app:app
