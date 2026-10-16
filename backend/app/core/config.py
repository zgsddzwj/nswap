from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "dev"  # dev | prod
    database_url: str = "sqlite:///./nswap.db"
    public_base_url: str = "http://127.0.0.1:8000"
    # mock: 本地开发全部通过; cloud: 云托管内免 access_token; token: 自管 token
    wx_call_mode: str = "mock"
    wx_appid: str = ""
    wx_secret: str = ""
    msg_tpl_want: str = ""
    msg_tpl_accepted: str = ""
    msg_tpl_confirm: str = ""
    msg_tpl_review: str = ""
    admin_session_secret: str = "dev-secret"
    enable_scheduler: bool = True
    upload_dir: str = "./uploads"

    # ---- 生产化加固（docs/09）----
    environment: str = "dev"  # dev | prod（Sentry 标签）
    # 图片存储：local=容器本地盘（仅开发）/ cos=腾讯云对象存储（生产必须，容器无状态）
    storage_backend: str = "local"
    cos_secret_id: str = ""
    cos_secret_key: str = ""
    cos_region: str = ""
    cos_bucket: str = ""
    cos_cdn_domain: str = ""  # 可选：CDN 加速域名（空则用 COS 默认域名）
    # 可观测性：DSN 为空则不启用 Sentry（本地零影响）
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1
    # 限流：pytest 关闭，生产开启
    rate_limit_enabled: bool = True
    # 协议版本（与小程序 agreement 页文案一致，变更即触发用户重新同意）
    terms_version: str = "2026-10"
    # 邻里墙（住户发帖）Phase 2 开关：社交类目过审后开启（docs/10 §3）
    neighbor_wall_enabled: bool = False

    # ---- 自建服务器登录（docs/13 路线 C）----
    # 登录 token 签名密钥：留空则复用 admin_session_secret（两者都须强随机）
    auth_token_secret: str = ""
    # token 有效期（默认 30 天）；过期后小程序 wx.login 静默重登，用户无感
    auth_token_max_age_seconds: int = 30 * 24 * 3600


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
