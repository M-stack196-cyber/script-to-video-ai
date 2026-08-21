"""Persistent models for multi-scene video generation jobs."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VideoJobStatus(str, Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    GENERATING_VIDEO = "generating_video"
    VIDEO_READY = "video_ready"
    GENERATING_AUDIO = "generating_audio"
    COMPOSING = "composing"
    COMPLETED = "completed"
    FAILED = "failed"


class SceneJobStatus(str, Enum):
    QUEUED = "queued"
    SUBMITTED = "submitted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class SceneJob(BaseModel):
    scene_number: int = Field(ge=1)
    prompt: str = Field(min_length=1)
    duration: float | None = None
    narration: str | None = None
    overlay_text: str | None = None
    invocation_arn: str | None = None
    status: SceneJobStatus = SceneJobStatus.QUEUED
    output_s3_uri: str | None = None
    local_video_path: str | None = None
    video_downloaded: bool = False
    error: str | None = None


class VideoJob(BaseModel):
    job_id: str = Field(min_length=1)
    status: VideoJobStatus
    progress: int = Field(ge=0, le=100)
    message: str
    mode: Literal["ai", "demo"]
    script: str = Field(min_length=1)
    duration: int = Field(gt=0)
    aspect_ratio: Literal["9:16", "16:9", "1:1"]
    scenes: list[SceneJob] = Field(default_factory=list)
    narration_provider: str | None = None
    final_video_url: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
