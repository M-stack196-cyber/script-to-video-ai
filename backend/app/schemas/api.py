from typing import Literal

from pydantic import BaseModel, Field, field_validator


class VideoPlanRequest(BaseModel):
    script: str
    duration: int = Field(gt=0)
    aspect_ratio: Literal["9:16", "16:9", "1:1"]

    @field_validator("script")
    @classmethod
    def validate_script(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("script cannot be empty")
        return value.strip()


class GenerateSceneRequest(BaseModel):
    prompt: str
    seed: int = 42

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt cannot be empty")
        return value.strip()


class GenerateSceneResponse(BaseModel):
    status: Literal["submitted"]
    invocation_arn: str


class ConfigStatusResponse(BaseModel):
    app_env: str
    job_store_provider: str
    media_storage_provider: str
    production_storage_ready: bool
    local_media_enabled: bool
    text_model_configured: bool
    video_model_configured: bool
    audio_model_configured: bool
    s3_configured: bool
    mock_scene_planner: bool
    narration_provider: str
    nova_sonic_sdk_available: bool
    standard_aws_credentials_detected: bool


class DeploymentReadinessResponse(BaseModel):
    ready: bool
    app_env: str
    frontend_ready: bool
    scene_planner_ready: bool
    video_generation_ready: bool
    durable_job_storage_ready: bool
    media_storage_ready: bool
    narration_ready: bool
    local_demo_available: bool
    blockers: list[str]


class MockRenderResponse(BaseModel):
    job_id: str
    mode: Literal["mock"]
    video_url: str
    scene_count: int
    total_duration: int
    aspect_ratio: Literal["9:16", "16:9", "1:1"]


class CreateVideoJobRequest(VideoPlanRequest):
    mode: Literal["ai"] = "ai"
