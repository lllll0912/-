FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BILL_DATA_DIR=/data \
    PORT=8501 \
    PYTHONPATH=/app/脚本:/app/账单:/app/账单/bills:/app/诗词:/app/诗词/poems:/app/喝水:/app/医疗:/app/日志

COPY 脚本/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data

EXPOSE 8501

CMD gunicorn -b 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 120 "webapp:app"
