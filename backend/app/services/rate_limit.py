"""轻量限流（docs/09 P0-2）。

内存滑动窗口实现：单实例准确；多实例部署需替换为 Redis 实现（接口已抽象）。
"""

import time
from collections import defaultdict, deque
from typing import Protocol

from app.core.config import settings


class RateLimiter(Protocol):
    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        """记一次访问。返回 True=放行，False=超限。"""
        ...


class MemoryRateLimiter:
    """滑动窗口计数（每 key 一个时间戳队列）。"""

    def __init__(self) -> None:
        self._events: dict[str, deque] = defaultdict(deque)

    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        q = self._events[key]
        cutoff = now - window_seconds
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        # 惰性清理：防止 key 无限增长（超过 10000 个 key 时清理空队列）
        if len(self._events) > 10000:
            for k in [k for k, v in self._events.items() if not v]:
                self._events.pop(k, None)
        return True

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._events.clear()
        else:
            self._events.pop(key, None)


_limiter: MemoryRateLimiter | None = None


def get_rate_limiter() -> MemoryRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = MemoryRateLimiter()
    return _limiter


def check_rate(key: str, limit: int, window_seconds: int) -> bool:
    """统一入口：限流关闭时永远放行（测试环境）。"""
    if not settings.rate_limit_enabled:
        return True
    return get_rate_limiter().hit(key, limit, window_seconds)


class FailureTracker:
    """连续失败追踪（登录防爆破，docs/09 P0-2）：窗口内失败达到阈值即锁定。"""

    def __init__(self) -> None:
        self._fail: dict[str, deque] = defaultdict(deque)

    def count(self, key: str, window_seconds: int) -> int:
        q = self._fail[key]
        cutoff = time.time() - window_seconds
        while q and q[0] < cutoff:
            q.popleft()
        return len(q)

    def record(self, key: str, window_seconds: int) -> int:
        self._fail[key].append(time.time())
        return self.count(key, window_seconds)

    def clear(self, key: str) -> None:
        self._fail.pop(key, None)


_failures: FailureTracker | None = None


def get_failure_tracker() -> FailureTracker:
    global _failures
    if _failures is None:
        _failures = FailureTracker()
    return _failures
