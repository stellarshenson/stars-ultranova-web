"""
Application configuration loaded from environment variables.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file="project.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    app_name: str = "Stars Nova Web"
    version: str = "0.1.0"
    debug: bool = True

    # Server
    host: str = "0.0.0.0"
    port: int = 9800
    reload: bool = True

    # CORS
    cors_origins: list[str] = ["http://localhost:9800", "http://127.0.0.1:9800"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    # Database (SQLite for now)
    database_url: str = "sqlite:///stars_nova.db"

    # Game Settings
    max_players: int = 16
    universe_sizes: list[str] = ["tiny", "small", "medium", "large", "huge"]
    default_universe_size: str = "medium"

    # Frontend
    frontend_dir: str = "frontend"
    static_files: bool = True


settings = Settings()
