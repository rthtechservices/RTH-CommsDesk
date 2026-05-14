from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RTH CommsDesk"
    env: str = "local"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./commsdesk.db"

    gmail_client_secrets_file: str = "./client_secret.json"
    gmail_token_file: str = "./gmail_token.json"
    gmail_account: str = "me"
    gmail_read_max_results: int = 100
    gmail_store_full_body: bool = False

    ai_provider: str = "mock"
    openai_api_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
