import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.schemas.job import SceneJobStatus, VideoJobStatus  # noqa: E402
from app.schemas.scene import Scene, ScenePlan  # noqa: E402
from app.services import job_store, media_paths  # noqa: E402
from app.workflows.ai_video_workflow import (  # noqa: E402
    create_ai_video_job,
    download_completed_scene_videos,
    refresh_video_job,
    submit_video_scenes,
)


def _plan() -> ScenePlan:
    scenes = []
    for number, start in ((1, 0.0), (2, 6.0)):
        scenes.append(
            Scene(
                scene_number=number,
                start_time=start,
                end_time=start + 6.0,
                duration=6.0,
                narration=f"Narration {number}",
                visual_description=f"Visual {number}",
                video_prompt=f"Safe mocked prompt {number}",
                camera_movement="Slow push",
                overlay_text=f"Scene {number}",
            )
        )
    return ScenePlan(total_duration=12, aspect_ratio="16:9", scenes=scenes)


def _create_test_job():
    with patch(
        "app.workflows.ai_video_workflow.generate_scene_plan",
        return_value=_plan(),
    ) as planner:
        job = create_ai_video_job("A two-scene test", 12, "16:9")
    planner.assert_called_once()
    assert job.status == VideoJobStatus.QUEUED
    assert len(job.scenes) == 2
    return job


def test_ai_video_workflow_without_aws() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="ai-workflow-"))
    original_directory = job_store.JOB_STORE_DIRECTORY
    original_bucket = settings.s3_bucket_name
    job_store.JOB_STORE_DIRECTORY = temporary_directory
    settings.s3_bucket_name = "mock-test-bucket"
    try:
        job = _create_test_job()
        with patch(
            "app.workflows.ai_video_workflow.start_video_generation",
            side_effect=["arn:mock:scene-1", "arn:mock:scene-2"],
        ) as submit:
            job = submit_video_scenes(job.job_id)
        assert submit.call_count == 2
        assert job.status == VideoJobStatus.GENERATING_VIDEO
        assert [scene.invocation_arn for scene in job.scenes] == [
            "arn:mock:scene-1",
            "arn:mock:scene-2",
        ]
        assert all(scene.status == SceneJobStatus.SUBMITTED for scene in job.scenes)

        with patch(
            "app.workflows.ai_video_workflow.get_video_generation_status",
            side_effect=[
                {"status": "Completed", "outputDataConfig": {"s3OutputDataConfig": {"s3Uri": "s3://mock/one"}}},
                {"status": "InProgress"},
            ],
        ):
            job = refresh_video_job(job.job_id)
        assert job.status == VideoJobStatus.GENERATING_VIDEO
        assert job.progress == 50
        assert job.scenes[0].output_s3_uri == "s3://mock/one"
        assert job.scenes[1].status == SceneJobStatus.IN_PROGRESS

        with patch(
            "app.workflows.ai_video_workflow.get_video_generation_status",
            return_value={"status": "Completed", "outputS3Uri": "s3://mock/two"},
        ):
            job = refresh_video_job(job.job_id)
        assert job.status == VideoJobStatus.VIDEO_READY
        assert job.progress == 100
        assert job.scenes[1].output_s3_uri == "s3://mock/two"
    finally:
        settings.s3_bucket_name = original_bucket
        job_store.JOB_STORE_DIRECTORY = original_directory
        shutil.rmtree(temporary_directory, ignore_errors=True)


def test_failed_scene_fails_whole_job() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="ai-workflow-failure-"))
    original_directory = job_store.JOB_STORE_DIRECTORY
    original_bucket = settings.s3_bucket_name
    job_store.JOB_STORE_DIRECTORY = temporary_directory
    settings.s3_bucket_name = "mock-test-bucket"
    try:
        job = _create_test_job()
        with patch(
            "app.workflows.ai_video_workflow.start_video_generation",
            side_effect=["arn:mock:one", "arn:mock:two"],
        ):
            job = submit_video_scenes(job.job_id)
        with patch(
            "app.workflows.ai_video_workflow.get_video_generation_status",
            side_effect=[
                {"status": "InProgress"},
                {"status": "Failed", "failureMessage": "Mock generation failure"},
            ],
        ):
            job = refresh_video_job(job.job_id)
        assert job.status == VideoJobStatus.FAILED
        assert job.scenes[1].status == SceneJobStatus.FAILED
        assert "Mock generation failure" in (job.error or "")
    finally:
        settings.s3_bucket_name = original_bucket
        job_store.JOB_STORE_DIRECTORY = original_directory
        shutil.rmtree(temporary_directory, ignore_errors=True)


def test_submission_failure_is_persisted() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="ai-submit-failure-"))
    original_directory = job_store.JOB_STORE_DIRECTORY
    original_bucket = settings.s3_bucket_name
    job_store.JOB_STORE_DIRECTORY = temporary_directory
    settings.s3_bucket_name = "mock-test-bucket"
    try:
        job = _create_test_job()
        with patch(
            "app.workflows.ai_video_workflow.start_video_generation",
            side_effect=["arn:mock:first", RuntimeError("Mock submission failure")],
        ):
            job = submit_video_scenes(job.job_id)
        assert job.status == VideoJobStatus.FAILED
        assert job.scenes[0].invocation_arn == "arn:mock:first"
        assert job.scenes[0].status == SceneJobStatus.SUBMITTED
        assert job.scenes[1].status == SceneJobStatus.FAILED
        assert "Mock submission failure" in (job.error or "")
        persisted = job_store.get_job(job.job_id)
        assert persisted.status == VideoJobStatus.FAILED
    finally:
        settings.s3_bucket_name = original_bucket
        job_store.JOB_STORE_DIRECTORY = original_directory
        shutil.rmtree(temporary_directory, ignore_errors=True)


def test_missing_s3_prevents_submission() -> None:
    original_bucket = settings.s3_bucket_name
    settings.s3_bucket_name = ""
    try:
        with patch("app.workflows.ai_video_workflow.start_video_generation") as submit:
            try:
                submit_video_scenes("never-loaded")
            except RuntimeError as exc:
                assert "S3_BUCKET_NAME" in str(exc)
            else:
                raise AssertionError("Expected missing S3 configuration failure")
        submit.assert_not_called()
    finally:
        settings.s3_bucket_name = original_bucket


def test_download_two_completed_scenes_and_skip_existing() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="ai-download-"))
    original_directory = job_store.JOB_STORE_DIRECTORY
    original_output_root = media_paths.OUTPUT_ROOT
    job_store.JOB_STORE_DIRECTORY = temporary_directory / "store"
    media_paths.OUTPUT_ROOT = temporary_directory / "output"
    try:
        job = _create_test_job()
        job.status = VideoJobStatus.VIDEO_READY
        for scene in job.scenes:
            scene.status = SceneJobStatus.COMPLETED
            scene.output_s3_uri = f"s3://mock/prefix-{scene.scene_number}/"

        existing = media_paths.scene_video_path(job.job_id, 1)
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_bytes(b"existing-video")
        job.scenes[0].local_video_path = media_paths.output_relative_path(existing)
        job_store.update_job(job)

        def mocked_download(_uri: str, destination: Path) -> Path:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"downloaded-video")
            return destination

        with patch(
            "app.workflows.ai_video_workflow.find_generated_video_object",
            return_value="s3://mock/final.mp4",
        ) as find_object, patch(
            "app.workflows.ai_video_workflow.download_s3_video",
            side_effect=mocked_download,
        ) as download:
            job = download_completed_scene_videos(job.job_id)

        assert find_object.call_count == 1
        assert download.call_count == 1
        assert job.status == VideoJobStatus.VIDEO_READY
        assert job.message == "All AI scene clips are downloaded locally"
        assert all(scene.video_downloaded for scene in job.scenes)
        assert all(scene.local_video_path for scene in job.scenes)
        assert not Path(job.scenes[1].local_video_path or "").is_absolute()
        downloaded = media_paths.resolve_output_path(job.scenes[1].local_video_path or "")
        assert downloaded.read_bytes() == b"downloaded-video"
    finally:
        media_paths.OUTPUT_ROOT = original_output_root
        job_store.JOB_STORE_DIRECTORY = original_directory
        shutil.rmtree(temporary_directory, ignore_errors=True)


def test_failed_download_persists_job_failure() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="ai-download-failure-"))
    original_directory = job_store.JOB_STORE_DIRECTORY
    original_output_root = media_paths.OUTPUT_ROOT
    job_store.JOB_STORE_DIRECTORY = temporary_directory / "store"
    media_paths.OUTPUT_ROOT = temporary_directory / "output"
    try:
        job = _create_test_job()
        job.status = VideoJobStatus.VIDEO_READY
        for scene in job.scenes:
            scene.status = SceneJobStatus.COMPLETED
            scene.output_s3_uri = f"s3://mock/prefix-{scene.scene_number}/"
        job_store.update_job(job)

        with patch(
            "app.workflows.ai_video_workflow.find_generated_video_object",
            side_effect=RuntimeError("Mock S3 listing failure"),
        ), patch("app.workflows.ai_video_workflow.download_s3_video") as download:
            try:
                download_completed_scene_videos(job.job_id)
            except RuntimeError as exc:
                assert "Mock S3 listing failure" in str(exc)
            else:
                raise AssertionError("Expected mocked download failure")
        download.assert_not_called()
        persisted = job_store.get_job(job.job_id)
        assert persisted.status == VideoJobStatus.FAILED
        assert persisted.scenes[0].video_downloaded is False
        assert "Mock S3 listing failure" in (persisted.scenes[0].error or "")
    finally:
        media_paths.OUTPUT_ROOT = original_output_root
        job_store.JOB_STORE_DIRECTORY = original_directory
        shutil.rmtree(temporary_directory, ignore_errors=True)


if __name__ == "__main__":
    test_ai_video_workflow_without_aws()
    test_failed_scene_fails_whole_job()
    test_submission_failure_is_persisted()
    test_missing_s3_prevents_submission()
    test_download_two_completed_scenes_and_skip_existing()
    test_failed_download_persists_job_failure()
    print("AI video workflow tests: SUCCESS")
