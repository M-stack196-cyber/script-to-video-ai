"""Atomic JSON-file persistence for local video job development."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from app.schemas.job import VideoJob, utc_now


JOB_STORE_DIRECTORY = Path(__file__).resolve().parents[2] / "output" / "jobs"


class JobNotFoundError(LookupError):
    """Raised when a requested local job does not exist."""


class JobStoreError(RuntimeError):
    """Raised when a local job cannot be persisted or validated."""


def _job_path(job_id: str) -> Path:
    if not job_id or Path(job_id).name != job_id or job_id in {".", ".."}:
        raise ValueError("job_id must be a non-empty file-safe identifier")
    return JOB_STORE_DIRECTORY / f"{job_id}.json"


def _write_job(job: VideoJob, *, require_new: bool) -> VideoJob:
    destination = _job_path(job.job_id)
    JOB_STORE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    if require_new and destination.exists():
        raise JobStoreError(f"Job already exists: {job.job_id}")

    job.updated_at = utc_now()
    temporary = JOB_STORE_DIRECTORY / f".{job.job_id}.{uuid4().hex}.tmp"
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


def create_job(job: VideoJob) -> VideoJob:
    return _write_job(job, require_new=True)


def update_job(job: VideoJob) -> VideoJob:
    destination = _job_path(job.job_id)
    if not destination.is_file():
        raise JobNotFoundError(f"Job not found: {job.job_id}")
    return _write_job(job, require_new=False)


def get_job(job_id: str) -> VideoJob:
    path = _job_path(job_id)
    if not path.is_file():
        raise JobNotFoundError(f"Job not found: {job_id}")
    try:
        return VideoJob.model_validate_json(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise JobStoreError(f"Could not read job {job_id}: {exc}") from exc
    except ValidationError as exc:
        raise JobStoreError(f"Stored job {job_id} is invalid: {exc}") from exc


def list_jobs(limit: int = 20) -> list[VideoJob]:
    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    if not JOB_STORE_DIRECTORY.exists():
        return []
    jobs: list[VideoJob] = []
    for path in JOB_STORE_DIRECTORY.glob("*.json"):
        try:
            jobs.append(VideoJob.model_validate_json(path.read_text(encoding="utf-8")))
        except (OSError, ValidationError) as exc:
            raise JobStoreError(f"Stored job file is invalid ({path.name}): {exc}") from exc
    jobs.sort(key=lambda job: job.updated_at, reverse=True)
    return jobs[:limit]


def delete_job(job_id: str) -> None:
    path = _job_path(job_id)
    if not path.is_file():
        raise JobNotFoundError(f"Job not found: {job_id}")
    try:
        path.unlink()
    except OSError as exc:
        raise JobStoreError(f"Could not delete job {job_id}: {exc}") from exc
