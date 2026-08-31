FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BILL_DATA_DIR=/data \
    PORT=8501 \
    PYTHONPATH=/app/脚本:/app/账单:/app/账单/bills:/app/诗词:/app/诗词/poems:/app/喝水:/app/医疗:/app/日志:/app/收藏

# 先装依赖（利用层缓存）
COPY 脚本/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 只拷代码与轻量 meta，不拷大图（收藏 pics / 医疗原件）
COPY 脚本/ /app/脚本/
COPY 账单/ /app/账单/
COPY 诗词/ /app/诗词/
COPY 喝水/ /app/喝水/
COPY 日志/ /app/日志/
COPY 医疗/health/ /app/医疗/health/
COPY 医疗/数据/_meta/ /app/医疗/数据/_meta/
COPY 收藏/collection/ /app/收藏/collection/
COPY 收藏/数据/_meta/ /app/收藏/数据/_meta/
COPY 收藏/README.md /app/收藏/README.md

WORKDIR /app/脚本

RUN mkdir -p /data

EXPOSE 8501

CMD gunicorn -b 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 120 "webapp:app"
