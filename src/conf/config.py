"""Application settings loaded from the environment (or a local .env file).

Every secret lives in the environment; nothing confidential is written in
the code. ``SECRET_KEY`` has no default on purpose: the app refuses to start
without one instead of silently signing tokens with a known value.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = (
        "postgresql+psycopg2://postgres:hw11secret@localhost:5432/contacts_app"
    )

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # Redis, used to cache the authenticated user between requests. With
    # redis unreachable the app quietly falls back to querying PostgreSQL.
    redis_url: str = "redis://localhost:6379/0"
    user_cache_ttl_seconds: int = 900

    # SMTP for the verification email. With mail_server left empty the app
    # logs the confirmation link instead of sending it, so everything is
    # testable without a mailbox.
    mail_username: str = ""
    mail_password: str = ""
    mail_from: str = "noreply@example.com"
    mail_server: str = ""
    mail_port: int = 587
    mail_from_name: str = "Contacts API"

    # Cloudinary for avatar uploads.
    cloudinary_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # Comma-separated list of origins allowed by CORS.
    cors_origins: str = "http://localhost:3000,http://localhost:8000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
