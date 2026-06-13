"""
config.py
---------
All environment variables are read here via pydantic-settings.
Import `settings` anywhere in the app — never read os.environ directly.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Find .env relative to this file — works regardless of where uvicorn is launched from
ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"
    ANTHROPIC_API_KEY: str
    S3_BUCKET: str = "sangatna-dev"
    S3_ENDPOINT_URL: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-south-1"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


settings = Settings()