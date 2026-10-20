import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

import app.models  # noqa: F401  确保所有模型注册到 Base.metadata
from app.api import api_router
from app.api.admin import admin_api_router  # SSR 路由已在 React 重构（docs/08 M5）中移除
from app.core.config import settings
from app.core.errors import ApiError, api_error_handler
from app.core.middleware import GlobalRateLimitMiddleware, RequestContextMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# ---- Sentry（docs/09 P0-5）：DSN 为空则完全不启用（本地零影响）----
if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
    )
    logging.getLogger(__name__).info("Sentry 已启用（environment=%s）", settings.environment)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 会话密钥守卫（docs/12 P0-2）：生产环境拒绝默认/空密钥启动——
    # SessionMiddleware 是签名 cookie，密钥公开即等于管理后台裸奔
    if settings.env == "prod":
        weak = {"", "dev-secret", "please-change-me-to-random-string", "change-me"}
        if settings.admin_session_secret in weak:
            raise RuntimeError(
                "生产环境 ADMIN_SESSION_SECRET 不能为空或默认值，请在环境变量中配置强随机串"
            )
    scheduler = None
    if settings.enable_scheduler:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler

            from app.db import SessionLocal
            from app.services.expiry import run_expiry_scan

            scheduler = BackgroundScheduler()

            def expiry_job():
                db = SessionLocal()
                try:
                    run_expiry_scan(db)
                finally:
                    db.close()

            scheduler.add_job(expiry_job, "cron", hour=3, minute=0)
            scheduler.start()
        except Exception as e:  # pragma: no cover
            logging.warning("定时任务启动失败（不影响服务）: %s", e)
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="nswap API", version="1.0.0", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.admin_session_secret)
app.add_middleware(GlobalRateLimitMiddleware)
app.add_middleware(RequestContextMiddleware)  # 最外层：日志/RequestId 覆盖全部请求
app.add_exception_handler(ApiError, api_error_handler)
app.include_router(api_router)
app.include_router(admin_api_router)

os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

# ---- 管理后台 SPA（admin-web/dist，docs/08 §7）：注册在所有 API 路由之后 ----
from fastapi.responses import FileResponse

# 本地：仓库根/admin-web/dist（三层）；容器：/app/admin-web/dist（两层）
_admin_dist = next(
    (
        p
        for p in [
            Path(__file__).resolve().parent.parent / "admin-web" / "dist",
            Path(__file__).resolve().parent.parent.parent / "admin-web" / "dist",
        ]
        if (p / "index.html").exists()
    ),
    None,
)
if _admin_dist:
    app.mount("/admin/assets", StaticFiles(directory=_admin_dist / "assets"), name="admin-assets")

    @app.get("/admin", include_in_schema=False)
    def admin_index():
        return FileResponse(_admin_dist / "index.html")

    @app.get("/admin/{path:path}", include_in_schema=False)
    def admin_spa(path: str):
        return FileResponse(_admin_dist / "index.html")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
