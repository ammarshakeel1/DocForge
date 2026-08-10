from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(default="", alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_storage_bucket: str = Field(default="invoices", alias="SUPABASE_STORAGE_BUCKET")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    api_cors_origins: str = Field(default="http://localhost:3000", alias="API_CORS_ORIGINS")
    confidence_threshold: float = Field(default=0.8, alias="CONFIDENCE_THRESHOLD")

    def require_supabase(self) -> None:
        missing = []
        if not self.supabase_url:
            missing.append("SUPABASE_URL")
        if not self.supabase_service_role_key:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        if missing:
            raise RuntimeError(
                "Missing required env vars: "
                + ", ".join(missing)
                + ". Copy .env.example to .env and fill in your Supabase project values."
            )

    def require_openai(self) -> None:
        if not self.openai_api_key:
            raise RuntimeError(
                "Missing OPENAI_API_KEY. Copy .env.example to .env and add your OpenAI key."
            )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
