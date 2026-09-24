# Backend API + worker image (FastAPI, RQ, PyMuPDF, Tesseract OCR)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus tesseract-ocr-uzb \
      fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ .
RUN useradd --system --uid 10001 --home /app app \
 && mkdir -p /data/uploads && chown -R app /data /app
USER app

ENV STORAGE_DIR=/data/uploads
EXPOSE 8000
# The API container runs migrations before starting; the worker overrides CMD.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --workers ${API_WORKERS:-2}"]
