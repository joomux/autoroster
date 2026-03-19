FROM python:3.12-slim

# System dependencies:
#   tesseract-ocr  — required by pytesseract
#   libgl1 / libglib2.0-0 — required by opencv-python-headless
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run injects $PORT at runtime (default 8080)
EXPOSE 8080

CMD exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --timeout 60 app:app
