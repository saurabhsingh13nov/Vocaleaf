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
    elevenlabs_tts_model: str = "eleven_multilingual_v2"

    # Anthropic / Claude
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Google OAuth
    google_client_id: str = ""

    # Google Gemini image generation
    google_genai_api_key: str = ""
    gemini_image_model: str | None = None
    imagen_model: str | None = None

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

    @property
    def resolved_gemini_image_model(self) -> str:
        return (
            self.gemini_image_model
            or self.imagen_model
            or "gemini-3.1-flash-image-preview"
        )


settings = Settings()
