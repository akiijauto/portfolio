FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py core.py ./
ENV PORT=8000 WORKERS=2
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --retries=20 \
  CMD curl -fsS http://localhost:8000/healthz || exit 1
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT} --workers ${WORKERS} --log-level warning --no-access-log"]
