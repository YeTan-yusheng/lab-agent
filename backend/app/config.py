from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # 数据库配置
    database_url: str
    test_database_url: str | None = None
    # JWT 配置
    jwt_secret_key: str
    jwt_expire_hours: int = 24
    jwt_algorithm: str = "HS256"
    # LLM 配置
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    # 种子数据
    app_env: str = "development"
    seed_default_password: str | None = None
    # 日志配置
    log_level: str = "INFO"
    log_format: str = "text"
    log_color: bool = False
    log_to_file: bool = False
    log_dir: str = "logs"
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 5
    slow_request_ms: int = 2000

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
    )


settings = Settings()

MAX_FILE_SIZE = 1024 * 1024 * 100
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
}
