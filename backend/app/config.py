from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Script to Video AI"
    app_env: str = "development"
    public_base_url: str = ""
    job_store_provider: str = "local"

    aws_region: str = "us-east-1"

    bedrock_text_model_id: str = ""
    bedrock_video_model_id: str = ""
    bedrock_audio_model_id: str = ""

    narration_provider: str = "local"

    use_mock_scene_planner: bool = False

    s3_bucket_name: str = ""

    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip() and origin.strip() != "*"
        ]

    @property
    def normalized_app_env(self) -> str:
        return self.app_env.strip().lower() or "development"

    @property
    def normalized_job_store_provider(self) -> str:
        return self.job_store_provider.strip().lower() or "local"

    @property
    def is_production(self) -> bool:
        return self.normalized_app_env == "production"

    @property
    def local_media_enabled(self) -> bool:
        return not self.is_production

    @property
    def production_storage_ready(self) -> bool:
        # Local JSON files are useful for development, but are not durable
        # production storage. No durable provider is implemented yet.
        return not self.is_production and self.normalized_job_store_provider == "local"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
