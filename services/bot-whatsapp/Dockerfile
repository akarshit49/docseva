# #genai: Sprint 5 / WS-E — Dockerfile for the WhatsApp adapter.
FROM python:3.12-slim

WORKDIR /app

# Minimal runtime deps (curl for healthcheck).
RUN apt-get update \
  && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    PORT=8080

EXPOSE 8080

# uvicorn pinned to a single worker — webhooks are stateless and the
# conversation state lives in Redis, so add workers behind a load balancer
# in production.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
