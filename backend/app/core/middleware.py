"""中间件：RequestId + 结构化访问日志 + 全局限流（docs/09 P0-2/P0-5）。"""

import json
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.services.rate_limit import check_rate

logger = logging.getLogger("nswap.access")

SLOW_REQUEST_SECONDS = 1.0
GLOBAL_RATE_LIMIT = 120  # 每 IP 每分钟
RATE_WINDOW = 60


def _client_ip(request: Request) -> str:
    # 云托管/反代场景优先取转发头
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """注入 X-Request-Id，记录结构化访问日志，慢请求 WARNING。"""

    async def dispatch(self, request: Request, call_next):
        request_id = uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        start = time.time()
        response = await call_next(request)
        elapsed_ms = int((time.time() - start) * 1000)
        response.headers["X-Request-Id"] = request_id
        level = logging.WARNING if elapsed_ms > SLOW_REQUEST_SECONDS * 1000 else logging.INFO
        logger.log(
            level,
            json.dumps(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "elapsed_ms": elapsed_ms,
                    "ip": _client_ip(request),
                },
                ensure_ascii=False,
            ),
        )
        return response


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """全局兜底限流：每 IP 每分钟 120 次（静态资源与健康检查豁免）。"""

    EXEMPT_PREFIXES = ("/admin/assets", "/uploads", "/healthz")

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            ip = _client_ip(request)
            if not check_rate(f"global:{ip}", GLOBAL_RATE_LIMIT, RATE_WINDOW):
                return JSONResponse(
                    status_code=429,
                    content={"code": 429, "message": "请求过于频繁，请稍后再试"},
                )
        return await call_next(request)
