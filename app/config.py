from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="APP_",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "astra-qa-backend"
    debug: bool = False

    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/astra_qa")
    redis_url: str = Field(default="redis://localhost:6379/0")
    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672/")

    cors_origins: list[str] = Field(default=["http://localhost:3000", "http://localhost:5173"])

    oidc_issuer_url: str = Field(default="https://sso.example.com/realms/astra")
    oidc_client_id: str = Field(default="astra-qa-backend")
    oidc_client_secret: SecretStr = Field(default=SecretStr(""))

    llm_provider: str = Field(default="gigachat")
    llm_api_key: SecretStr = Field(default=SecretStr(""))
    llm_model_name: str = Field(default="GigaChat:latest")
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=8192, ge=1)
    llm_request_timeout_seconds: int = Field(default=60, ge=1)

    minio_endpoint: str = Field(default="localhost:9000")
    minio_access_key: str = Field(default="minioadmin")
    minio_secret_key: SecretStr = Field(default=SecretStr("minioadmin"))
    minio_secure: bool = Field(default=False)

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=4, ge=1)

    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")

    jira_base_url: str | None = Field(default=None)
    jira_token: SecretStr | None = Field(default=None)

    gitlab_base_url: str | None = Field(default=None)
    gitlab_token: SecretStr | None = Field(default=None)

    opensearch_url: str | None = Field(default=None)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
