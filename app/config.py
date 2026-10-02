"""Application configuration management using pydantic-settings."""

from functools import lru_cache
from typing import List, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "GitHub Description Generator"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = Field(default="production", description="Environment: development | production")
    DEBUG: bool = False

    # Server Binding & Subpath
    HOST: str = "127.0.0.1"
    PORT: int = 8085
    ROOT_PATH: str = Field(
        default="",
        description="ASGI root_path for subpath proxy (e.g. /tool/github-description)",
    )

    # Security & CORS
    CORS_ORIGINS: Union[str, List[str]] = "*"
    RATE_LIMIT_PER_MINUTE: int = 60

    # Logging
    LOG_LEVEL: str = "INFO"

    # GitHub Defaults
    GITHUB_DEFAULT_TOKEN: str = ""

    # AI Model Providers
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.strip() == "*":
                return ["*"]
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
