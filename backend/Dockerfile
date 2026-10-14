# ---- 阶段 1：管理后台前端构建（docs/08 §7） ----
FROM node:20-alpine AS web
WORKDIR /web
COPY admin-web/package.json admin-web/package-lock.json ./
RUN npm install --registry=https://registry.npmmirror.com --no-audit --no-fund
COPY admin-web/ ./
RUN npm run build

# ---- 阶段 2：后端 ----
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/
COPY --from=web /web/dist /app/admin-web/dist

# uploads 目录（云托管容器文件系统为临时存储，生产建议切换对象存储，见 docs/03）
RUN mkdir -p /app/uploads

EXPOSE 8000

# 启动前执行数据库迁移
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
