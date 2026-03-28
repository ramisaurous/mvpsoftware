# app/core/config.py
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GM_SUV_", extra="ignore")

    database_url: str = "sqlite:///./gm_suv_shop.db"
    storage_dir: str = "./app/storage"
    max_upload_mb: int = 25


settings = Settings()
