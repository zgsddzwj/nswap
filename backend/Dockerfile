# ---- 阶段 1：管理后台前端构建（docs/08 §7） ----
FROM node:20-alpine AS web
WORKDIR /web
# 管理后台部署前缀：默认 /admin（FastAPI 同源挂载）；
# 子路径隔离部署（nginx 网关下）传 --build-arg ADMIN_BASE=/nswap/admin
ARG ADMIN_BASE=/admin
COPY admin-web/package.json admin-web/package-lock.json ./
RUN npm install --registry=https://registry.npmmirror.com --no-audit --no-fund
COPY admin-web/ ./
RUN ADMIN_BASE=${ADMIN_BASE} npm run build

# ---- 阶段 2：后端 ----
FROM python:3.11-slim

WORKDIR /app

# pip 镜像源：国内服务器直连 PyPI 极慢，默认清华源；海外部署可
# docker build --build-arg PIP_INDEX=https://pypi.org/simple 覆盖
ARG PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -i ${PIP_INDEX} -r requirements.txt

COPY backend/ /app/
COPY --from=web /web/dist /app/admin-web/dist

# uploads 目录（本地存储后端用；生产请配置 STORAGE_BACKEND=cos，见 docs/09 P0-1）
RUN mkdir -p /app/uploads

# 非 root 运行（docs/09 P1-12）
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"

# 启动前执行数据库迁移
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
