import shutil
import sys
import tempfile
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.schemas.job import VideoJob, VideoJobStatus  # noqa: E402
from app.storage.job_store import (  # noqa: E402
    JobNotFoundError,
    JobStoreError,
    LocalJobStore,
    get_job_store,
)


def _job(job_id: str, message: str = "Ready") -> VideoJob:
    return VideoJob(
        job_id=job_id,
        status=VideoJobStatus.QUEUED,
        progress=0,
        message=message,
        mode="ai",
        script="An isolated local persistence test.",
        duration=12,
        aspect_ratio="16:9",
    )


def _expect(exception_type, operation) -> Exception:
    try:
        operation()
    except exception_type as exc:
        return exc
    raise AssertionError(f"Expected {exception_type.__name__}")


def test_local_job_store_lifecycle_and_ordering() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="job-store-"))
    try:
        store = LocalJobStore(temporary_directory)
        first = store.create(_job("first-job"))
        second = store.create(_job("second-job"))
        assert store.get("first-job") == first
        assert [job.job_id for job in store.list()] == ["second-job", "first-job"]

        first.progress = 50
        first.message = "Updated"
        store.update(first)
        assert store.get("first-job").progress == 50
        assert [job.job_id for job in store.list(limit=1)] == ["first-job"]
        assert not list(temporary_directory.glob("*.tmp"))
        assert not list(temporary_directory.glob(".*.tmp"))

        store.delete("first-job")
        _expect(JobNotFoundError, lambda: store.get("first-job"))
        _expect(JobNotFoundError, lambda: store.delete("first-job"))
    finally:
        shutil.rmtree(temporary_directory, ignore_errors=True)


def test_local_job_store_errors_are_explicit() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="job-store-errors-"))
    try:
        store = LocalJobStore(temporary_directory)
        job = store.create(_job("duplicate-job"))
        _expect(JobStoreError, lambda: store.create(job))
        _expect(JobNotFoundError, lambda: store.get("missing-job"))
        _expect(JobNotFoundError, lambda: store.update(_job("missing-job")))
        for invalid_id in ("", "../escape", "nested/job", ".", ".."):
            _expect(ValueError, lambda value=invalid_id: store.get(value))
        _expect(ValueError, lambda: store.list(limit=0))

        malformed_path = temporary_directory / "malformed.json"
        malformed_path.write_text("{not valid json", encoding="utf-8")
        _expect(JobStoreError, lambda: store.get("malformed"))
        _expect(JobStoreError, lambda: store.list())
    finally:
        shutil.rmtree(temporary_directory, ignore_errors=True)


def test_job_store_factory() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="job-store-factory-"))
    original_provider = settings.job_store_provider
    try:
        settings.job_store_provider = "local"
        store = get_job_store(temporary_directory)
        assert isinstance(store, LocalJobStore)
        assert store.root_directory == temporary_directory
        settings.job_store_provider = "dynamodb"
        try:
            get_job_store(temporary_directory)
        except RuntimeError as exc:
            assert "Unsupported JOB_STORE_PROVIDER" in str(exc)
        else:
            raise AssertionError("Expected unsupported job-store provider to fail")
    finally:
        settings.job_store_provider = original_provider
        shutil.rmtree(temporary_directory, ignore_errors=True)


if __name__ == "__main__":
    test_local_job_store_lifecycle_and_ordering()
    test_local_job_store_errors_are_explicit()
    test_job_store_factory()
    print("Job store tests: SUCCESS")
