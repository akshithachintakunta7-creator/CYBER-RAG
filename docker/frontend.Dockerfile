FROM python:3.11-slim

WORKDIR /app

COPY requirements-frontend.txt .
RUN pip install --default-timeout=200 --no-cache-dir -r requirements-frontend.txt

COPY frontend/ ./frontend/

RUN addgroup --system --gid 1001 appuser && \
    adduser --system --uid 1001 --gid 1001 appuser
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8501

CMD ["streamlit", "run", "frontend/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]