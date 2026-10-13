FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# uploads 目录（云托管容器文件系统为临时存储，生产建议切换对象存储，见 docs/03）
RUN mkdir -p /app/uploads

EXPOSE 8000

# 启动前执行数据库迁移
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
