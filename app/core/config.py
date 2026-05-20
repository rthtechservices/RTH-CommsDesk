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
    gmail_write_enabled: bool = False
    gmail_draft_create_enabled: bool = False
    gmail_send_enabled: bool = False
    gmail_label_archive_enabled: bool = False
    gmail_noise_label_id: str | None = None
    microsoft_tenant_id: str | None = None
    microsoft_client_id: str | None = None
    microsoft_client_secret: str | None = None
    microsoft_account: str = "me"
    microsoft_graph_enabled: bool = False
    microsoft_graph_auth_mode: str = "app_only"
    microsoft_graph_scopes: str = "User.Read Mail.Read offline_access"
    microsoft_graph_token_file: str = "./microsoft_graph_token.json"
    microsoft_graph_outlook_mail_enabled: bool = False
    microsoft_graph_teams_enabled: bool = False
    microsoft_graph_outlook_calendar_read_enabled: bool = False
    microsoft_graph_base_url: str = "https://graph.microsoft.com/v1.0"
    notification_webhook_secret: str | None = None

    ai_provider: str = "mock"
    openai_api_key: str | None = None
    ai_model: str | None = None
    ai_base_url: str = "https://api.openai.com/v1"
    ai_timeout_seconds: float = 20.0
    ai_max_tokens: int = 1200
    ai_temperature: float = 0.2
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_deployment: str | None = None
    azure_openai_api_version: str = "2025-04-01-preview"
    calendar_provider: str = "mock"
    google_calendar_token_file: str = "./google_calendar_token.json"
    google_calendar_id: str = "primary"
    google_calendar_time_zone: str = "America/Vancouver"
    google_calendar_read_enabled: bool = False
    google_calendar_write_enabled: bool = False
    outlook_calendar_read_enabled: bool = False
    execution_provider: str = "mock"
    external_write_dry_run: bool = True
    operational_test_mode: bool = False
    execution_test_email_allowlist: str = ""

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
    backup_include_oauth_tokens: bool = False
    backup_include_env_file: bool = False

    # Life-to-date stats go-live baseline (ISO timestamp or blank until initialized)
    app_stats_go_live_at: str | None = None

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
