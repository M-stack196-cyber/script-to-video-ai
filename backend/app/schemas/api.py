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
    text_model_configured: bool
    video_model_configured: bool
    audio_model_configured: bool
    s3_configured: bool
    mock_scene_planner: bool
