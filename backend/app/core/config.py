from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://loteria:loteria@localhost:5432/loteria_predictor"
    environment: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
