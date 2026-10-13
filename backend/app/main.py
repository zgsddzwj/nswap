import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

import app.models  # noqa: F401  确保所有模型注册到 Base.metadata
from app.api import api_router
from app.api.admin.routes import router as admin_router
from app.core.config import settings
from app.core.errors import ApiError, api_error_handler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
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
app.add_exception_handler(ApiError, api_error_handler)
app.include_router(api_router)
app.include_router(admin_router)

os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
