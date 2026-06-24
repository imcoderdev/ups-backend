from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "iot-ups-backend"
    environment: str = "development"
    log_level: str = "INFO"

    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_key: str = Field(default="", alias="SUPABASE_KEY")

    simulator_api_url: str = Field(default="http://127.0.0.1:8000", alias="SIMULATOR_API_URL")
    simulator_device_count: int = Field(default=3, alias="SIMULATOR_DEVICE_COUNT")
    simulator_interval_seconds: float = Field(default=3.0, alias="SIMULATOR_INTERVAL_SECONDS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
