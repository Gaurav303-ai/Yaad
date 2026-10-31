"""Application settings loaded from the server environment."""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    embeddings_provider: str = "voyage"
    voyage_api_key: str | None = None
    supabase_url: str = ""
    supabase_secret_key: str = ""
    tracker: str | None = None
    trello_key: str | None = None
    trello_token: str | None = None
    trello_list_id: str | None = None
    github_token: str | None = None
    github_repo: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    resend_api_key: str | None = None
    digest_from_email: str | None = None
    app_env: str = "development"
    client_url: str = "http://localhost:5173"
    cron_secret: str | None = None
    demo_mode: bool = False

    @model_validator(mode="after")
    def require_core_credentials(self) -> "Settings":
        required = {
            "GEMINI_API_KEY": self.gemini_api_key,
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_SECRET_KEY": self.supabase_secret_key,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            names = ", ".join(missing)
            raise ValueError(f"Missing required server environment values: {names}. Set them in server/.env.local.")
        return self


settings = Settings()
