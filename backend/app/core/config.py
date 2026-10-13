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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
