from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Script to Video AI"

    aws_region: str = "us-east-1"

    bedrock_text_model_id: str = ""
    bedrock_video_model_id: str = ""
    bedrock_audio_model_id: str = ""

    use_mock_scene_planner: bool = False

    s3_bucket_name: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
