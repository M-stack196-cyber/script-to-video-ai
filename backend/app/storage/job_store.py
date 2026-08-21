"""Job persistence interface, local implementation, and provider factory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from pydantic import ValidationError

from app.config import settings
from app.schemas.job import VideoJob, utc_now


DEFAULT_JOB_STORE_DIRECTORY = Path(__file__).resolve().parents[2] / "output" / "jobs"


class JobNotFoundError(LookupError):
    """Raised when a requested job does not exist."""


class JobStoreError(RuntimeError):
    """Raised when a job cannot be persisted or validated."""


class JobStore(Protocol):
    def create(self, job: VideoJob) -> VideoJob: ...
    def update(self, job: VideoJob) -> VideoJob: ...
    def get(self, job_id: str) -> VideoJob: ...
    def list(self, limit: int = 20) -> list[VideoJob]: ...
    def delete(self, job_id: str) -> None: ...


class LocalJobStore:
    """Atomic JSON job persistence rooted at a configurable local directory."""

    def __init__(self, root_directory: str | Path = DEFAULT_JOB_STORE_DIRECTORY):
        self.root_directory = Path(root_directory)

    def _job_path(self, job_id: str) -> Path:
        if not job_id or Path(job_id).name != job_id or job_id in {".", ".."}:
            raise ValueError("job_id must be a non-empty file-safe identifier")
        return self.root_directory / f"{job_id}.json"

    def _write(self, job: VideoJob, *, require_new: bool) -> VideoJob:
        destination = self._job_path(job.job_id)
        self.root_directory.mkdir(parents=True, exist_ok=True)
        if require_new and destination.exists():
            raise JobStoreError(f"Job already exists: {job.job_id}")
        job.updated_at = utc_now()
        temporary = self.root_directory / f".{job.job_id}.{uuid4().hex}.tmp"
        try:
            temporary.write_text(
                json.dumps(job.model_dump(mode="json"), indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(destination)
        except OSError as exc:
            raise JobStoreError(f"Could not persist job {job.job_id}: {exc}") from exc
        finally:
            temporary.unlink(missing_ok=True)
        return job

    def create(self, job: VideoJob) -> VideoJob:
        return self._write(job, require_new=True)

    def update(self, job: VideoJob) -> VideoJob:
        if not self._job_path(job.job_id).is_file():
            raise JobNotFoundError(f"Job not found: {job.job_id}")
        return self._write(job, require_new=False)

    def get(self, job_id: str) -> VideoJob:
        path = self._job_path(job_id)
        if not path.is_file():
            raise JobNotFoundError(f"Job not found: {job_id}")
        try:
            return VideoJob.model_validate_json(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise JobStoreError(f"Could not read job {job_id}: {exc}") from exc
        except ValidationError as exc:
            raise JobStoreError(f"Stored job {job_id} is invalid: {exc}") from exc

    def list(self, limit: int = 20) -> list[VideoJob]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if not self.root_directory.exists():
            return []
        jobs: list[VideoJob] = []
        for path in self.root_directory.glob("*.json"):
            try:
                jobs.append(VideoJob.model_validate_json(path.read_text(encoding="utf-8")))
            except (OSError, ValidationError) as exc:
                raise JobStoreError(
                    f"Stored job file is invalid ({path.name}): {exc}"
                ) from exc
        jobs.sort(key=lambda job: job.updated_at, reverse=True)
        return jobs[:limit]

    def delete(self, job_id: str) -> None:
        path = self._job_path(job_id)
        if not path.is_file():
            raise JobNotFoundError(f"Job not found: {job_id}")
        try:
            path.unlink()
        except OSError as exc:
            raise JobStoreError(f"Could not delete job {job_id}: {exc}") from exc


def get_job_store(root_directory: str | Path | None = None) -> JobStore:
    provider = settings.normalized_job_store_provider
    if provider == "local":
        return LocalJobStore(root_directory or DEFAULT_JOB_STORE_DIRECTORY)
    raise RuntimeError(f"Unsupported JOB_STORE_PROVIDER: {provider}")
