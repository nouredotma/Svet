from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str = Field(..., alias="REDIS_URL")
    qdrant_url: str = Field(..., alias="QDRANT_URL")
    qdrant_collection_name: str = Field("dexter_memory", alias="QDRANT_COLLECTION_NAME")

    llm_api_key: str | None = Field(None, alias="LLM_API_KEY")
    llm_model: str = Field("gemini-2.5-flash", alias="LLM_MODEL")
    llm_base_url: str = Field(
        "https://generativelanguage.googleapis.com/v1beta/openai/",
        alias="LLM_BASE_URL",
    )

    secret_key: str = Field(..., alias="SECRET_KEY")

    default_llm_provider: str = Field("gemini", alias="DEFAULT_LLM_PROVIDER")

    sentry_dsn: str | None = Field(None, alias="SENTRY_DSN")
    environment: str = Field("dev", alias="ENVIRONMENT")

    serpapi_key: str | None = Field(None, alias="SERPAPI_KEY")

    agent_files_root: str = Field("/tmp/dexter_agent_files", alias="AGENT_FILES_ROOT")

    smtp_host: str | None = Field(None, alias="SMTP_HOST")
    smtp_port: int = Field(587, alias="SMTP_PORT")
    smtp_user: str | None = Field(None, alias="SMTP_USER")
    smtp_password: str | None = Field(None, alias="SMTP_PASSWORD")
    smtp_from: str = Field("noreply@localhost", alias="SMTP_FROM")
    imap_host: str | None = Field(None, alias="IMAP_HOST")
    imap_port: int = Field(993, alias="IMAP_PORT")
    imap_user: str | None = Field(None, alias="IMAP_USER")
    imap_password: str | None = Field(None, alias="IMAP_PASSWORD")

    max_prompt_chars: int = Field(12000, alias="MAX_PROMPT_CHARS")
    max_tool_input_chars: int = Field(6000, alias="MAX_TOOL_INPUT_CHARS")

    cors_origins: str = Field("*", alias="CORS_ORIGINS")
    google_calendar_access_token: str | None = Field(None, alias="GOOGLE_CALENDAR_ACCESS_TOKEN")
    google_calendar_id: str = Field("primary", alias="GOOGLE_CALENDAR_ID")


@lru_cache
def get_settings() -> Settings:
    return Settings()
