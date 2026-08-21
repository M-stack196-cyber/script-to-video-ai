"""Portable local output paths for persisted video job media."""

from __future__ import annotations

import re
from pathlib import Path


OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "output"
_SAFE_JOB_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def validate_job_id(job_id: str) -> str:
    if not job_id or not _SAFE_JOB_ID.fullmatch(job_id):
        raise ValueError("job_id must contain only letters, numbers, hyphens, or underscores")
    return job_id


def job_media_directory(job_id: str) -> Path:
    return OUTPUT_ROOT / "jobs" / validate_job_id(job_id) / "media"


def scene_video_path(job_id: str, scene_number: int) -> Path:
    if scene_number < 1:
        raise ValueError("scene_number must be greater than zero")
    return job_media_directory(job_id) / f"scene_{scene_number:03d}.mp4"


def scene_normalized_video_path(job_id: str, scene_number: int) -> Path:
    if scene_number < 1:
        raise ValueError("scene_number must be greater than zero")
    return job_media_directory(job_id) / f"scene_{scene_number:03d}_normalized.mp4"


def scene_audio_path(job_id: str, scene_number: int) -> Path:
    if scene_number < 1:
        raise ValueError("scene_number must be greater than zero")
    return job_media_directory(job_id) / f"scene_{scene_number:03d}_narration.wav"


def scene_composed_path(job_id: str, scene_number: int) -> Path:
    if scene_number < 1:
        raise ValueError("scene_number must be greater than zero")
    return job_media_directory(job_id) / f"scene_{scene_number:03d}_composed.mp4"


def final_video_path(job_id: str) -> Path:
    return job_media_directory(job_id) / "final.mp4"


def output_relative_path(path: str | Path) -> str:
    candidate = Path(path).resolve()
    try:
        return candidate.relative_to(OUTPUT_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("Media path must be inside the backend output directory") from exc


def resolve_output_path(relative_path: str) -> Path:
    if not relative_path or Path(relative_path).is_absolute():
        raise ValueError("Stored media path must be relative to the backend output directory")
    candidate = (OUTPUT_ROOT / relative_path).resolve()
    try:
        candidate.relative_to(OUTPUT_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("Stored media path escapes the backend output directory") from exc
    return candidate
