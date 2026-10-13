import logging
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

API_BASE = "https://api.weixin.qq.com"


class WechatError(Exception):
    pass


class WechatClient:
    """微信开放接口统一封装。

    三种模式（WX_CALL_MODE）：
    - mock:  本地开发/测试，全部直接通过（调用方按返回 None 处理）
    - cloud: 云托管容器内运行，调 api.weixin.qq.com 免 access_token（开放接口服务）
    - token: 自管 access_token（自建服务器部署，需 WX_APPID/WX_SECRET）
    """

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    # ---------- 底层 ----------

    def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at - 120:
            return self._access_token
        resp = httpx.get(
            f"{API_BASE}/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": settings.wx_appid,
                "secret": settings.wx_secret,
            },
            timeout=10,
        )
        data = resp.json()
        if "access_token" not in data:
            raise WechatError(f"get access_token failed: {data}")
        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + int(data.get("expires_in", 7200))
        return self._access_token

    def _post(self, path: str, payload: dict) -> dict:
        mode = settings.wx_call_mode
        if mode == "cloud":
            resp = httpx.post(f"{API_BASE}{path}", json=payload, timeout=10)
        elif mode == "token":
            token = self._get_access_token()
            resp = httpx.post(
                f"{API_BASE}{path}", params={"access_token": token}, json=payload, timeout=10
            )
        else:
            return {}
        return resp.json()

    # ---------- 业务接口 ----------

    def code2session(self, js_code: str) -> dict:
        """备用登录通道（callContainer 注入 X-WX-OPENID 时不需要）。"""
        if settings.wx_call_mode == "mock":
            return {"openid": f"mock-{js_code}"}
        resp = httpx.get(
            f"{API_BASE}/sns/jscode2session",
            params={
                "appid": settings.wx_appid,
                "secret": settings.wx_secret,
                "js_code": js_code,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        return resp.json()

    def msg_sec_check(self, content: str, openid: str) -> str:
        """文本内容安全。返回 'pass' | 'risk' | 'error'（error 时调用方走降级）。"""
        if settings.wx_call_mode == "mock" or not content.strip():
            return "pass"
        try:
            data = self._post(
                "/wxa/msg_sec_check",
                {"content": content, "version": 2, "scene": 2, "openid": openid},
            )
        except (httpx.HTTPError, WechatError) as e:
            logger.warning("msg_sec_check error: %s", e)
            return "error"
        if data.get("errcode") == 0:
            suggest = (data.get("result") or {}).get("suggest", "pass")
            return "pass" if suggest == "pass" else "risk"
        if data.get("errcode") in (87014,):  # 内容违规
            return "risk"
        logger.warning("msg_sec_check unexpected: %s", data)
        return "error"

    def media_check_async(self, media_url: str, openid: str) -> str | None:
        """图片异步安全检测。返回 trace_id；mock 模式返回 None（调用方直接置 pass）。"""
        if settings.wx_call_mode == "mock":
            return None
        try:
            data = self._post(
                "/wxa/media_check_async",
                {"media_url": media_url, "media_type": 2, "version": 2, "scene": 2, "openid": openid},
            )
        except (httpx.HTTPError, WechatError) as e:
            logger.warning("media_check_async error: %s", e)
            return None
        if data.get("errcode") == 0:
            return data.get("trace_id")
        logger.warning("media_check_async unexpected: %s", data)
        return None

    def send_subscribe_message(
        self, openid: str, template_id: str, data: dict[str, str], page: str | None = None
    ) -> None:
        if settings.wx_call_mode == "mock" or not template_id:
            return
        payload = {
            "touser": openid,
            "template_id": template_id,
            "page": page or "pages/home/index",
            "miniprogram_state": "formal",
            "data": {k: {"value": v} for k, v in data.items()},
        }
        try:
            resp = self._post("/cgi-bin/message/subscribe/send", payload)
            if resp.get("errcode") != 0:
                logger.warning("subscribe send failed: %s", resp)
        except (httpx.HTTPError, WechatError) as e:
            logger.warning("subscribe send error: %s", e)


client = WechatClient()
