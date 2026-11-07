import os
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "Predictive DevOps Intelligence Platform"
    APP_ENV: str = Field(default="development")
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True
    SECRET_KEY: str = Field(default="dev-insecure-secret-key-change-in-prod-min-32-chars")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/devops_intelligence"
    )
    SYNC_DATABASE_URL: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/devops_intelligence"
    )

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_STREAM_EVENTS: str = "stream:devops:events"
    REDIS_CONSUMER_GROUP: str = "group:devops:intelligence"

    # Integrations
    GITHUB_WEBHOOK_SECRET: str = Field(default="test-github-webhook-secret")
    GITHUB_API_TOKEN: str = Field(default="")

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    # Metrics
    ENABLE_METRICS: bool = True


settings = Settings()
