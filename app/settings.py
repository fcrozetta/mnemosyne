from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    arango_scheme: str = "http"
    arango_host: str = "localhost"
    arango_port: int = 8529
    arango_db: str = "mnemosyne"
    arango_username: str = "root"
    arango_root_password: str = "root"
    api_port: int = 8000

    @computed_field  # type: ignore[prop-decorator]
    @property
    def arango_hosts(self) -> str:
        return f"{self.arango_scheme}://{self.arango_host}:{self.arango_port}"

    @property
    def arango_password(self) -> str:
        return self.arango_root_password


__all__ = ["Settings"]
