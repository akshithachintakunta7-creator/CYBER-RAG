FROM python:3.11-slim

WORKDIR /app

ENV HOME=/app
ENV TRANSFORMERS_CACHE=/app/.cache
ENV HF_HOME=/app/.cache
ENV XDG_CACHE_HOME=/app/.cache

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install torch (CPU-only, much smaller)
RUN pip install --default-timeout=200 --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Copy and install backend requirements
COPY requirements-backend.txt .
RUN pip install --default-timeout=200 --no-cache-dir -r requirements-backend.txt

COPY backend/ ./backend/
COPY .env .env

RUN addgroup --system --gid 1001 appuser && \
    adduser --system --uid 1001 --gid 1001 appuser

RUN mkdir -p /app/.cache && chown -R appuser:appuser /app/.cache
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]