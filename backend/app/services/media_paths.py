"""Backward-compatible media helpers backed by the configured provider."""

from pathlib import Path

from app.storage.media_storage import DEFAULT_OUTPUT_ROOT, get_media_storage


OUTPUT_ROOT = DEFAULT_OUTPUT_ROOT


def _storage():
    return get_media_storage(Path(OUTPUT_ROOT))


def validate_job_id(job_id: str) -> str:
    return _storage().validate_job_id(job_id)


def job_media_directory(job_id: str) -> Path:
    return _storage().job_media_directory(job_id)


def scene_video_path(job_id: str, scene_number: int) -> Path:
    return _storage().scene_video_path(job_id, scene_number)


def scene_normalized_video_path(job_id: str, scene_number: int) -> Path:
    return _storage().scene_normalized_video_path(job_id, scene_number)


def scene_audio_path(job_id: str, scene_number: int) -> Path:
    return _storage().scene_audio_path(job_id, scene_number)


def scene_composed_path(job_id: str, scene_number: int) -> Path:
    return _storage().scene_composed_path(job_id, scene_number)


def final_video_path(job_id: str) -> Path:
    return _storage().final_video_path(job_id)


def output_relative_path(path: str | Path) -> str:
    return _storage().stored_reference(path)


def resolve_output_path(relative_path: str) -> Path:
    return _storage().resolve_reference(relative_path)


def output_public_url(relative_path: str) -> str:
    return _storage().public_url(relative_path)
