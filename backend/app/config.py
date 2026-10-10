from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    database_url: str

    jwt_secret_key: str
    jwt_expire_hours: int = 24
    jwt_algorithm: str = "HS256"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
    )


settings = Settings()