import shutil
import sys
import tempfile
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.storage.media_storage import (  # noqa: E402
    LocalMediaStorage,
    get_media_storage,
)


def _expect_value_error(operation) -> None:
    try:
        operation()
    except ValueError:
        return
    raise AssertionError("Expected ValueError")


def test_local_media_paths_and_references() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="media-storage-"))
    try:
        storage = LocalMediaStorage(temporary_directory)
        media_directory = temporary_directory / "jobs" / "job_123" / "media"
        assert storage.job_media_directory("job_123") == media_directory
        assert storage.scene_video_path("job_123", 1) == media_directory / "scene_001.mp4"
        assert storage.scene_normalized_video_path("job_123", 2) == (
            media_directory / "scene_002_normalized.mp4"
        )
        assert storage.scene_audio_path("job_123", 3) == (
            media_directory / "scene_003_narration.wav"
        )
        assert storage.scene_composed_path("job_123", 4) == (
            media_directory / "scene_004_composed.mp4"
        )
        final_path = storage.final_video_path("job_123")
        assert final_path == media_directory / "final.mp4"
        reference = storage.stored_reference(final_path)
        assert reference == "jobs/job_123/media/final.mp4"
        assert storage.resolve_reference(reference) == final_path.resolve()
        assert storage.public_url(reference) == "/output/jobs/job_123/media/final.mp4"
    finally:
        shutil.rmtree(temporary_directory, ignore_errors=True)


def test_local_media_storage_rejects_unsafe_paths() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="media-storage-safety-"))
    try:
        storage = LocalMediaStorage(temporary_directory)
        for invalid_job_id in ("", "../escape", "nested/job", ".", "job id"):
            _expect_value_error(lambda value=invalid_job_id: storage.job_media_directory(value))
        _expect_value_error(lambda: storage.scene_video_path("safe-job", 0))
        _expect_value_error(lambda: storage.resolve_reference("../escape.mp4"))
        _expect_value_error(lambda: storage.resolve_reference("/absolute/video.mp4"))
        _expect_value_error(
            lambda: storage.stored_reference(temporary_directory.parent / "outside.mp4")
        )
        safe = storage.resolve_reference("jobs/safe-job/media/final.mp4")
        safe.relative_to(temporary_directory.resolve())
    finally:
        shutil.rmtree(temporary_directory, ignore_errors=True)


def test_media_storage_factory() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="media-factory-"))
    original_provider = settings.media_storage_provider
    try:
        settings.media_storage_provider = "local"
        storage = get_media_storage(temporary_directory)
        assert isinstance(storage, LocalMediaStorage)
        assert storage.output_root == temporary_directory
        settings.media_storage_provider = "s3"
        try:
            get_media_storage(temporary_directory)
        except RuntimeError as exc:
            assert "Unsupported MEDIA_STORAGE_PROVIDER" in str(exc)
        else:
            raise AssertionError("Expected unsupported media provider to fail")
    finally:
        settings.media_storage_provider = original_provider
        shutil.rmtree(temporary_directory, ignore_errors=True)


if __name__ == "__main__":
    test_local_media_paths_and_references()
    test_local_media_storage_rejects_unsafe_paths()
    test_media_storage_factory()
    print("Media storage tests: SUCCESS")
