import shutil
import sys
import tempfile
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.job import SceneJob, VideoJob, VideoJobStatus  # noqa: E402
from app.services import job_store  # noqa: E402


def test_json_job_persistence() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="job-store-"))
    original_directory = job_store.JOB_STORE_DIRECTORY
    job_store.JOB_STORE_DIRECTORY = temporary_directory
    try:
        job = VideoJob(
            job_id="test-job",
            status=VideoJobStatus.QUEUED,
            progress=0,
            message="Ready",
            mode="ai",
            script="A safely persisted local job.",
            duration=12,
            aspect_ratio="16:9",
            scenes=[SceneJob(scene_number=1, prompt="First scene")],
        )
        job_store.create_job(job)
        stored_path = temporary_directory / "test-job.json"
        assert stored_path.is_file()
        assert not list(temporary_directory.glob("*.tmp"))

        loaded = job_store.get_job("test-job")
        assert loaded == job
        assert loaded.created_at.tzinfo is not None
        loaded.progress = 50
        loaded.message = "Updated"
        job_store.update_job(loaded)
        assert job_store.get_job("test-job").progress == 50
        assert [item.job_id for item in job_store.list_jobs()] == ["test-job"]

        job_store.delete_job("test-job")
        try:
            job_store.get_job("test-job")
        except job_store.JobNotFoundError:
            pass
        else:
            raise AssertionError("Expected deleted job to be missing")
    finally:
        job_store.JOB_STORE_DIRECTORY = original_directory
        shutil.rmtree(temporary_directory, ignore_errors=True)


if __name__ == "__main__":
    test_json_job_persistence()
    print("Job store tests: SUCCESS")
