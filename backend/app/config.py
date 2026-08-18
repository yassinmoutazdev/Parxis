"""Application configuration using pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_list(value: str) -> list[str]:
    """Parse a comma-separated string into a list."""
    return [item.strip() for item in value.split(",")]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="PRAXIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database settings
    db_path: Path = Path("./data/praxis.db")

    # Obsidian vault path
    vault_path: Path = Path("./EnglishNotes")

    # Backup settings
    backup_dir: Path = Path("./data/backups")

    # Chat attachment settings (Epic B: ephemeral chat attachments)
    chat_attachments_dir: Path = Path("./data/chat_attachments")
    backup_retention_daily: int = 14
    backup_retention_monthly: int = 6

    # Ollama Cloud settings (Praxis is Ollama Cloud-only; there is no
    # unauthenticated local-server mode -- every request requires a real
    # OLLAMA_API_KEY, validated against this host). Cloud model tags need a
    # `-cloud` suffix when hit directly via https://ollama.com/api/*
    # (e.g. "gemma4:31b" locally -> "gemma4:31b-cloud" here) -- without
    # it, the direct cloud API won't resolve the model.
    ollama_host: str = "https://ollama.com"
    ollama_model: str = "gemma4:31b-cloud"
    ollama_api_key: str | None = None  # Optional API key for Ollama Cloud
    ollama_timeout_seconds: int = 120
    ollama_max_retries: int = 1

    # Logging
    log_level: str = "INFO"

    # API settings
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # CORS settings (comma-separated in env file)
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Watcher settings
    watcher_debounce_seconds: float = 2.0

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse cors_origins string into a list."""
        return _parse_list(self.cors_origins)


# Global settings instance
settings = Settings()
