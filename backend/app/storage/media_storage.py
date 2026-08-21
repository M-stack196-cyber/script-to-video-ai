"""Media storage interface, local implementation, and provider factory."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

from app.config import settings


DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "output"
_SAFE_JOB_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class MediaStorage(Protocol):
    output_root: Path
    def validate_job_id(self, job_id: str) -> str: ...
    def job_media_directory(self, job_id: str) -> Path: ...
    def scene_video_path(self, job_id: str, scene_number: int) -> Path: ...
    def scene_normalized_video_path(self, job_id: str, scene_number: int) -> Path: ...
    def scene_audio_path(self, job_id: str, scene_number: int) -> Path: ...
    def scene_composed_path(self, job_id: str, scene_number: int) -> Path: ...
    def final_video_path(self, job_id: str) -> Path: ...
    def stored_reference(self, path: str | Path) -> str: ...
    def resolve_reference(self, reference: str) -> Path: ...
    def public_url(self, reference: str) -> str: ...


class LocalMediaStorage:
    """Filesystem-backed media storage beneath a configured output root."""

    def __init__(self, output_root: str | Path = DEFAULT_OUTPUT_ROOT):
        self.output_root = Path(output_root)

    @staticmethod
    def validate_job_id(job_id: str) -> str:
        if not job_id or not _SAFE_JOB_ID.fullmatch(job_id):
            raise ValueError(
                "job_id must contain only letters, numbers, hyphens, or underscores"
            )
        return job_id

    @staticmethod
    def _validate_scene_number(scene_number: int) -> int:
        if scene_number < 1:
            raise ValueError("scene_number must be greater than zero")
        return scene_number

    def job_media_directory(self, job_id: str) -> Path:
        return self.output_root / "jobs" / self.validate_job_id(job_id) / "media"

    def scene_video_path(self, job_id: str, scene_number: int) -> Path:
        self._validate_scene_number(scene_number)
        return self.job_media_directory(job_id) / f"scene_{scene_number:03d}.mp4"

    def scene_normalized_video_path(self, job_id: str, scene_number: int) -> Path:
        self._validate_scene_number(scene_number)
        return self.job_media_directory(job_id) / f"scene_{scene_number:03d}_normalized.mp4"

    def scene_audio_path(self, job_id: str, scene_number: int) -> Path:
        self._validate_scene_number(scene_number)
        return self.job_media_directory(job_id) / f"scene_{scene_number:03d}_narration.wav"

    def scene_composed_path(self, job_id: str, scene_number: int) -> Path:
        self._validate_scene_number(scene_number)
        return self.job_media_directory(job_id) / f"scene_{scene_number:03d}_composed.mp4"

    def final_video_path(self, job_id: str) -> Path:
        return self.job_media_directory(job_id) / "final.mp4"

    def stored_reference(self, path: str | Path) -> str:
        candidate = Path(path).resolve()
        try:
            return candidate.relative_to(self.output_root.resolve()).as_posix()
        except ValueError as exc:
            raise ValueError("Media path must be inside the configured output root") from exc

    def resolve_reference(self, reference: str) -> Path:
        if not reference or Path(reference).is_absolute():
            raise ValueError("Stored media path must be relative to the configured output root")
        candidate = (self.output_root / reference).resolve()
        try:
            candidate.relative_to(self.output_root.resolve())
        except ValueError as exc:
            raise ValueError("Stored media path escapes the configured output root") from exc
        return candidate

    def public_url(self, reference: str) -> str:
        safe_reference = self.stored_reference(self.resolve_reference(reference))
        return f"/output/{safe_reference}"


def get_media_storage(output_root: str | Path | None = None) -> MediaStorage:
    provider = settings.normalized_media_storage_provider
    if provider == "local":
        return LocalMediaStorage(output_root or DEFAULT_OUTPUT_ROOT)
    raise RuntimeError(f"Unsupported MEDIA_STORAGE_PROVIDER: {provider}")
