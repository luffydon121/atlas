"""Runtime configuration, read from environment variables and the project .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ATLAS_", env_file=(BACKEND_DIR.parent / ".env"), extra="ignore"
    )

    data_dir: Path = BACKEND_DIR.parent / "data"
    public_read_only: bool = False
    passcode: str = ""
    host: str = "127.0.0.1"
    port: int = 8000

    sec_contact: str = ""
    fred_api_key: str = ""
    bls_api_key: str = ""
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    ollama_embed_model: str = ""

    scheduler_enabled: bool = True
    alert_interval_seconds: int = 300
    macos_notifications: bool = False
    max_upload_mb: int = 25

    @property
    def resolved_data_dir(self) -> Path:
        path = self.data_dir if self.data_dir.is_absolute() else (BACKEND_DIR / self.data_dir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.resolved_data_dir / 'atlas.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
