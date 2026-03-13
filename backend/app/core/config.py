from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "Vocaleaf"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://vocaleaf:vocaleaf_dev@localhost:5432/vocaleaf"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # ElevenLabs
    elevenlabs_api_key: str = ""
    elevenlabs_base_url: str = "https://api.elevenlabs.io"

    # Google OAuth
    google_client_id: str = ""

    # Cloudflare R2 / S3-compatible object storage
    r2_endpoint_url: str = ""
    r2_bucket_name: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_region: str = "auto"
    asset_upload_url_expire_seconds: int = 600
    asset_read_url_expire_seconds: int = 300
    voice_sample_max_file_size_bytes: int = 25 * 1024 * 1024

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7


settings = Settings()
