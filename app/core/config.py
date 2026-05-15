from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RTH CommsDesk"
    env: str = "local"
    log_level: str = "INFO"
    log_format: str = "plain"
    database_url: str = "sqlite:///./commsdesk.db"
    app_base_url: str = "http://127.0.0.1:8000"

    gmail_client_secrets_file: str = "./client_secret.json"
    gmail_token_file: str = "./gmail_token.json"
    gmail_account: str = "me"
    gmail_read_max_results: int = 100
    gmail_store_full_body: bool = False
    microsoft_tenant_id: str | None = None
    microsoft_client_id: str | None = None
    microsoft_client_secret: str | None = None
    microsoft_account: str = "me"
    notification_webhook_secret: str | None = None

    ai_provider: str = "mock"
    openai_api_key: str | None = None
    calendar_provider: str = "mock"
    google_calendar_read_enabled: bool = False
    outlook_calendar_read_enabled: bool = False

    app_auth_enabled: bool = False
    app_auth_username: str | None = None
    app_auth_password: str | None = None
    api_auth_token: str | None = None
    auth_session_cookie_name: str = "commsdesk_session"
    auth_session_secret: str = "local-dev-change-me"
    auth_session_ttl_hours: int = 12

    retention_message_body_days: int = 90
    retention_sent_learning_days: int = 180
    retention_execution_audit_days: int = 365

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def normalized_env(self) -> str:
        return self.env.strip().lower()

    @property
    def auth_required(self) -> bool:
        if self.app_auth_enabled:
            return True
        return self.normalized_env in {"staging", "production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
