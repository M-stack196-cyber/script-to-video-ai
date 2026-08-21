"""Backward-compatible job-store functions backed by the configured provider."""

from pathlib import Path
from app.schemas.job import VideoJob
from app.storage.job_store import (
    DEFAULT_JOB_STORE_DIRECTORY,
    JobNotFoundError,
    JobStoreError,
    get_job_store,
)


JOB_STORE_DIRECTORY = DEFAULT_JOB_STORE_DIRECTORY


def _store():
    return get_job_store(Path(JOB_STORE_DIRECTORY))


def create_job(job: VideoJob) -> VideoJob:
    return _store().create(job)


def update_job(job: VideoJob) -> VideoJob:
    return _store().update(job)


def get_job(job_id: str) -> VideoJob:
    return _store().get(job_id)


def list_jobs(limit: int = 20) -> list[VideoJob]:
    return _store().list(limit)


def delete_job(job_id: str) -> None:
    _store().delete(job_id)
