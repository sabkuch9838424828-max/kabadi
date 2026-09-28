"""Application configuration loaded from environment / .env."""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Kabadiwala Connect API"
    env: str = "development"
    debug: bool = True

    database_url: str = (
        "postgresql+psycopg2://kabadiwala:kabadiwala_dev_pw@127.0.0.1:5432/kabadiwala_connect"
    )

    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 1440
    jwt_algorithm: str = "HS256"

    cors_origins: str = (
        "http://localhost:12000,http://127.0.0.1:12000,"
        "http://localhost:12001,http://127.0.0.1:12001,"
        "http://localhost:5173,http://localhost:3000,http://localhost:3001"
    )

    model_path: str = ""
    allow_model_download: bool = True

    @field_validator("secret_key")
    @classmethod
    def _warn_secret(cls, v: str) -> str:
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.env.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
