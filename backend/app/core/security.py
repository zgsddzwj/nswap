import hashlib
import hmac
import os

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import settings

_AUTH_TOKEN_SALT = "auth-token-v1"


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return f"{salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split("$", 1)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 100_000)
    return hmac.compare_digest(dk.hex(), dk_hex)


# ---------- 登录 token（自建服务器模式，docs/13 路线 C）----------

def _auth_serializer() -> URLSafeTimedSerializer:
    secret = settings.auth_token_secret or settings.admin_session_secret
    return URLSafeTimedSerializer(secret, salt=_AUTH_TOKEN_SALT)


def create_auth_token(openid: str) -> str:
    """签发登录 token：签名 + 时间戳，无状态、不可伪造。"""
    return _auth_serializer().dumps({"openid": openid})


def read_auth_token(token: str, max_age: int | None = None) -> str | None:
    """校验 token 并返回 openid；过期或被篡改返回 None。"""
    try:
        data = _auth_serializer().loads(
            token, max_age=max_age or settings.auth_token_max_age_seconds
        )
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict):
        return None
    openid = data.get("openid")
    return str(openid) if openid else None
