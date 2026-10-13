from datetime import datetime, timezone


def utcnow() -> datetime:
    """秒级精度 UTC（MySQL DATETIME 默认精度为秒，游标分页依赖时间戳可比较）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.replace(microsecond=0).isoformat() + "Z"


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
