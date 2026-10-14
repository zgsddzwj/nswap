from app.api.admin.api import router as admin_api_router  # JSON API（/api/admin/*）
from app.api.admin.routes import router as admin_router  # SSR（M5 移除）

__all__ = ["admin_router", "admin_api_router"]
