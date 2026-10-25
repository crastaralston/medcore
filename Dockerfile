# One container serves the API and the built web app.

FROM node:22-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/ backend/
RUN pip install --no-cache-dir -e ./backend
COPY demo/ demo/
COPY --from=web /app/frontend/dist frontend/dist
ENV MEDCORE_DATA_DIR=/app/data MEDCORE_DEMO_DIR=/app/demo
EXPOSE 8000
CMD ["sh", "-c", "uvicorn medcore_verify.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
