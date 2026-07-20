FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BILL_DATA_DIR=/data \
    PORT=8501

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data

EXPOSE 8501

CMD gunicorn -b 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 120 "app:app"
