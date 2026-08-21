import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.job import (  # noqa: E402
    SceneJob,
    SceneJobStatus,
    VideoJob,
    VideoJobNextAction,
    VideoJobStatus,
)
from app.services import job_store  # noqa: E402
from app.workflows.video_orchestrator import (  # noqa: E402
    advance_video_job,
    create_video_workflow_job,
    determine_next_action,
    get_job_workflow_state,
)


def _job(status: VideoJobStatus, *, downloaded: bool = False) -> VideoJob:
    scene_status = (
        SceneJobStatus.COMPLETED
        if status in {
            VideoJobStatus.VIDEO_READY,
            VideoJobStatus.GENERATING_AUDIO,
            VideoJobStatus.COMPOSING,
            VideoJobStatus.COMPLETED,
        }
        else SceneJobStatus.QUEUED
    )
    return VideoJob(
        job_id=f"job-{status.value}",
        status=status,
        progress=100 if status == VideoJobStatus.COMPLETED else 0,
        message="Test job",
        mode="ai",
        script="Orchestrator test",
        duration=6,
        aspect_ratio="16:9",
        scenes=[
            SceneJob(
                scene_number=1,
                prompt="Mock prompt",
                duration=6,
                narration="Mock narration",
                status=scene_status,
                video_downloaded=downloaded,
                local_video_path=(
                    "jobs/test/media/scene_001.mp4" if downloaded else None
                ),
            )
        ],
    )


def test_next_action_matrix() -> None:
    assert determine_next_action(_job(VideoJobStatus.QUEUED)) == (
        VideoJobNextAction.SUBMIT_VIDEO
    )
    assert determine_next_action(_job(VideoJobStatus.GENERATING_VIDEO)) == (
        VideoJobNextAction.REFRESH
    )
    assert determine_next_action(_job(VideoJobStatus.VIDEO_READY)) == (
        VideoJobNextAction.DOWNLOAD_VIDEO
    )
    assert determine_next_action(
        _job(VideoJobStatus.VIDEO_READY, downloaded=True)
    ) == VideoJobNextAction.COMPOSE
    assert determine_next_action(_job(VideoJobStatus.COMPLETED)) == (
        VideoJobNextAction.COMPLETED
    )
    assert determine_next_action(_job(VideoJobStatus.FAILED)) == (
        VideoJobNextAction.NONE
    )


def test_get_state_and_single_step_advance() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="orchestrator-"))
    original_directory = job_store.JOB_STORE_DIRECTORY
    job_store.JOB_STORE_DIRECTORY = temporary_directory
    try:
        queued = _job(VideoJobStatus.QUEUED)
        job_store.create_job(queued)
        state = get_job_workflow_state(queued.job_id)
        assert state.next_action == VideoJobNextAction.SUBMIT_VIDEO
        assert state.can_submit_video is True
        assert state.is_terminal is False

        submitted = queued.model_copy(deep=True)
        submitted.status = VideoJobStatus.GENERATING_VIDEO
        submitted.scenes[0].status = SceneJobStatus.SUBMITTED
        with patch(
            "app.workflows.video_orchestrator.submit_video_scenes",
            return_value=submitted,
        ) as submit, patch(
            "app.workflows.video_orchestrator.refresh_video_job"
        ) as refresh, patch(
            "app.workflows.video_orchestrator.download_completed_scene_videos"
        ) as download, patch(
            "app.workflows.video_orchestrator.compose_ai_video_job"
        ) as compose:
            advanced = advance_video_job(queued.job_id)
        submit.assert_called_once_with(queued.job_id)
        refresh.assert_not_called()
        download.assert_not_called()
        compose.assert_not_called()
        assert advanced.next_action == VideoJobNextAction.REFRESH
    finally:
        job_store.JOB_STORE_DIRECTORY = original_directory
        shutil.rmtree(temporary_directory, ignore_errors=True)


def test_terminal_advance_is_idempotent() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="orchestrator-terminal-"))
    original_directory = job_store.JOB_STORE_DIRECTORY
    job_store.JOB_STORE_DIRECTORY = temporary_directory
    try:
        for status in (VideoJobStatus.COMPLETED, VideoJobStatus.FAILED):
            job = _job(status)
            job_store.create_job(job)
            with patch(
                "app.workflows.video_orchestrator.submit_video_scenes"
            ) as submit, patch(
                "app.workflows.video_orchestrator.refresh_video_job"
            ) as refresh, patch(
                "app.workflows.video_orchestrator.download_completed_scene_videos"
            ) as download, patch(
                "app.workflows.video_orchestrator.compose_ai_video_job"
            ) as compose:
                state = advance_video_job(job.job_id)
            submit.assert_not_called()
            refresh.assert_not_called()
            download.assert_not_called()
            compose.assert_not_called()
            assert state.is_terminal is True
            expected = (
                VideoJobNextAction.COMPLETED
                if status == VideoJobStatus.COMPLETED
                else VideoJobNextAction.NONE
            )
            assert state.next_action == expected
    finally:
        job_store.JOB_STORE_DIRECTORY = original_directory
        shutil.rmtree(temporary_directory, ignore_errors=True)


def test_workflow_creation_does_not_submit_video() -> None:
    created = _job(VideoJobStatus.QUEUED)
    with patch(
        "app.workflows.video_orchestrator.create_ai_video_job",
        return_value=created,
    ) as create, patch(
        "app.workflows.video_orchestrator.submit_video_scenes"
    ) as submit:
        state = create_video_workflow_job("Script", 6, "16:9")
    create.assert_called_once_with("Script", 6, "16:9")
    submit.assert_not_called()
    assert state.next_action == VideoJobNextAction.SUBMIT_VIDEO


if __name__ == "__main__":
    test_next_action_matrix()
    test_get_state_and_single_step_advance()
    test_terminal_advance_is_idempotent()
    test_workflow_creation_does_not_submit_video()
    print("Video orchestrator tests: SUCCESS")
