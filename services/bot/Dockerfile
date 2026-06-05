FROM python:3.12-slim

WORKDIR /app

# System deps for document processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libmagic1 curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies (build context is project root)
COPY services/bot/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the rembg AI model so first-use is instant
RUN python -c "from rembg import new_session; new_session('u2net')" || true

# Copy bot application code
COPY services/bot/ .

# Copy shared assets (company logo default)
RUN mkdir -p /app/assets
COPY assets/ /app/assets/

CMD ["python", "-m", "app.main"]
