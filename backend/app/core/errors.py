from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """业务异常：HTTP 状态码 + 业务消息。"""

    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(message)


def bad_request(message: str) -> ApiError:
    return ApiError(400, message)


def unauthorized(message: str = "请先登录") -> ApiError:
    return ApiError(401, message)


def forbidden(message: str = "没有权限执行此操作") -> ApiError:
    return ApiError(403, message)


def not_found(message: str = "内容不存在或已删除") -> ApiError:
    return ApiError(404, message)


def conflict(message: str) -> ApiError:
    return ApiError(409, message)


def too_many(message: str) -> ApiError:
    return ApiError(429, message)


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"code": exc.status, "message": exc.message})
