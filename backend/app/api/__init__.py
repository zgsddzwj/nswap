from fastapi import APIRouter

from app.api import (
    announcements,
    telemetry,
    auth,
    chat,
    community,
    favorites,
    gratitudes,
    items,
    messages,
    notifications,
    reports,
    trades,
    uploads,
    users,
    wants,
    wechat_callback,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(announcements.router)
api_router.include_router(telemetry.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(community.router)
api_router.include_router(items.router)
api_router.include_router(wants.router)
api_router.include_router(messages.router)
api_router.include_router(chat.router)
api_router.include_router(trades.router)
api_router.include_router(favorites.router)
api_router.include_router(gratitudes.router)
api_router.include_router(reports.router)
api_router.include_router(notifications.router)
api_router.include_router(uploads.router)
api_router.include_router(wechat_callback.router)
