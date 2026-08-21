import sys
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas.job import SceneJobStatus, VideoJobStatus  # noqa: E402
from app.schemas.scene import Scene, ScenePlan  # noqa: E402
from app.services import job_store, media_paths  # noqa: E402


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_local_vite_origin_is_allowed_by_cors() -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_config_status_contains_only_safe_fields() -> None:
    response = client.get("/api/config/status")

    assert response.status_code == 200
    assert set(response.json()) == {
        "text_model_configured",
        "video_model_configured",
        "audio_model_configured",
        "s3_configured",
        "mock_scene_planner",
        "narration_provider",
        "nova_sonic_sdk_available",
        "standard_aws_credentials_detected",
    }


def test_plan_video_with_mock_planner() -> None:
    original_mock_setting = settings.use_mock_scene_planner
    settings.use_mock_scene_planner = True
    try:
        response = client.post(
            "/api/video/plan",
            json={
                "script": "A simple product that saves time every day.",
                "duration": 12,
                "aspect_ratio": "9:16",
            },
        )
    finally:
        settings.use_mock_scene_planner = original_mock_setting

    assert response.status_code == 200
    scene_plan = response.json()
    assert scene_plan["total_duration"] == 12
    assert scene_plan["aspect_ratio"] == "9:16"
    assert len(scene_plan["scenes"]) == 2
    assert sum(scene["duration"] for scene in scene_plan["scenes"]) == 12


def test_demo_render_with_mock_planner() -> None:
    original_mock_setting = settings.use_mock_scene_planner
    settings.use_mock_scene_planner = True
    job_directory = None
    try:
        response = client.post(
            "/api/video/demo-render",
            json={
                "script": "A short local-only video demo.",
                "duration": 1,
                "aspect_ratio": "1:1",
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert result["mode"] == "mock"
        assert result["scene_count"] == 1
        assert result["video_url"].endswith("/final.mp4")
        video_response = client.get(result["video_url"])
        assert video_response.status_code == 200
        assert len(video_response.content) > 0
        job_directory = (BACKEND_ROOT / "output" / result["video_url"].removeprefix("/output/")).parent
    finally:
        settings.use_mock_scene_planner = original_mock_setting
        if job_directory is not None:
            shutil.rmtree(job_directory, ignore_errors=True)


def test_demo_render_rejects_real_mode() -> None:
    original_mock_setting = settings.use_mock_scene_planner
    settings.use_mock_scene_planner = False
    try:
        response = client.post(
            "/api/video/demo-render",
            json={"script": "No fallback", "duration": 1, "aspect_ratio": "1:1"},
        )
    finally:
        settings.use_mock_scene_planner = original_mock_setting
    assert response.status_code == 503


def _api_scene_plan() -> ScenePlan:
    return ScenePlan(
        total_duration=6,
        aspect_ratio="16:9",
        scenes=[
            Scene(
                scene_number=1,
                start_time=0,
                end_time=6,
                duration=6,
                narration="Mock narration",
                visual_description="Mock visual",
                video_prompt="Mock video prompt",
                camera_movement="Static",
                overlay_text="Mock",
            )
        ],
    )


def test_job_api_without_aws() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="job-api-"))
    original_directory = job_store.JOB_STORE_DIRECTORY
    original_output_root = media_paths.OUTPUT_ROOT
    original_bucket = settings.s3_bucket_name
    original_provider = settings.narration_provider
    job_store.JOB_STORE_DIRECTORY = temporary_directory
    media_paths.OUTPUT_ROOT = temporary_directory / "output"
    settings.s3_bucket_name = ""
    settings.narration_provider = "local"
    try:
        with patch(
            "app.workflows.ai_video_workflow.generate_scene_plan",
            return_value=_api_scene_plan(),
        ) as planner:
            response = client.post(
                "/api/jobs",
                json={
                    "script": "API orchestration test",
                    "duration": 6,
                    "aspect_ratio": "16:9",
                    "mode": "ai",
                },
            )
        planner.assert_called_once()
        assert response.status_code == 200
        job = response.json()
        assert job["status"] == "queued"
        assert len(job["scenes"]) == 1

        stored_response = client.get(f'/api/jobs/{job["job_id"]}')
        assert stored_response.status_code == 200
        assert stored_response.json()["job_id"] == job["job_id"]

        with patch("app.main.submit_video_scenes") as submit:
            submit_response = client.post(f'/api/jobs/{job["job_id"]}/submit-video')
        assert submit_response.status_code == 503
        submit.assert_not_called()

        unknown_response = client.get("/api/jobs/unknown-job")
        assert unknown_response.status_code == 404

        unknown_download = client.post("/api/jobs/unknown-job/download-video")
        assert unknown_download.status_code == 404

        unknown_compose = client.post("/api/jobs/unknown-job/compose")
        assert unknown_compose.status_code == 404

        invalid_download = client.post(f'/api/jobs/{job["job_id"]}/download-video')
        assert invalid_download.status_code == 409
        invalid_compose = client.post(f'/api/jobs/{job["job_id"]}/compose')
        assert invalid_compose.status_code == 409

        stored_job = job_store.get_job(job["job_id"])
        stored_job.status = VideoJobStatus.VIDEO_READY
        stored_job.scenes[0].status = SceneJobStatus.COMPLETED
        stored_job.scenes[0].output_s3_uri = "s3://mock-output/job-prefix/"
        job_store.update_job(stored_job)

        def mocked_download(_uri: str, destination: Path) -> Path:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"mock-api-video")
            return destination

        with patch(
            "app.workflows.ai_video_workflow.find_generated_video_object",
            return_value="s3://mock-output/job-prefix/final.mp4",
        ), patch(
            "app.workflows.ai_video_workflow.download_s3_video",
            side_effect=mocked_download,
        ):
            download_response = client.post(
                f'/api/jobs/{job["job_id"]}/download-video'
            )
        assert download_response.status_code == 200
        downloaded_job = download_response.json()
        assert downloaded_job["status"] == "video_ready"
        assert downloaded_job["scenes"][0]["video_downloaded"] is True
        assert not Path(downloaded_job["scenes"][0]["local_video_path"]).is_absolute()

        def mocked_media(_first, destination: Path, *_rest, **_kwargs) -> Path:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"mock-composed-media")
            return destination

        with patch(
            "app.workflows.ai_video_workflow.normalize_video_clip",
            side_effect=mocked_media,
        ), patch(
            "app.workflows.ai_video_workflow.generate_narration",
            side_effect=mocked_media,
        ), patch(
            "app.workflows.ai_video_workflow.mux_scene_narration",
            side_effect=lambda _video, _audio, destination, _duration: mocked_media(
                None, destination
            ),
        ), patch(
            "app.workflows.ai_video_workflow.concat_production_scenes",
            side_effect=lambda _scenes, destination: mocked_media(None, destination),
        ):
            compose_response = client.post(f'/api/jobs/{job["job_id"]}/compose')
        assert compose_response.status_code == 200
        composed_job = compose_response.json()
        assert composed_job["status"] == "completed"
        assert composed_job["progress"] == 100
        assert composed_job["final_video_url"].endswith("/media/final.mp4")
    finally:
        settings.s3_bucket_name = original_bucket
        settings.narration_provider = original_provider
        media_paths.OUTPUT_ROOT = original_output_root
        job_store.JOB_STORE_DIRECTORY = original_directory
        shutil.rmtree(temporary_directory, ignore_errors=True)


def test_workflow_api_without_aws() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="workflow-api-"))
    original_directory = job_store.JOB_STORE_DIRECTORY
    original_bucket = settings.s3_bucket_name
    original_video_model = settings.bedrock_video_model_id
    job_store.JOB_STORE_DIRECTORY = temporary_directory
    settings.s3_bucket_name = ""
    try:
        with patch(
            "app.workflows.ai_video_workflow.generate_scene_plan",
            return_value=_api_scene_plan(),
        ), patch(
            "app.workflows.ai_video_workflow.start_video_generation"
        ) as paid_submission:
            response = client.post(
                "/api/workflow/jobs",
                json={
                    "script": "Workflow API test",
                    "duration": 6,
                    "aspect_ratio": "16:9",
                },
            )
        paid_submission.assert_not_called()
        assert response.status_code == 200
        workflow = response.json()
        job_id = workflow["job"]["job_id"]
        assert workflow["next_action"] == "submit_video"
        assert workflow["stage"] == "waiting_to_submit"
        assert workflow["can_submit_video"] is True

        state_response = client.get(f"/api/workflow/jobs/{job_id}")
        assert state_response.status_code == 200
        assert state_response.json()["job"]["job_id"] == job_id

        unknown = client.get("/api/workflow/jobs/unknown-job")
        assert unknown.status_code == 404

        with patch(
            "app.workflows.video_orchestrator.submit_video_scenes"
        ) as submit:
            missing_config = client.post(
                f"/api/workflow/jobs/{job_id}/advance"
            )
        assert missing_config.status_code == 503
        submit.assert_not_called()

        settings.s3_bucket_name = "mock-bucket"
        settings.bedrock_video_model_id = "mock-video-model"
        submitted_job = job_store.get_job(job_id)
        submitted_job.status = VideoJobStatus.GENERATING_VIDEO
        submitted_job.scenes[0].status = SceneJobStatus.SUBMITTED
        with patch(
            "app.workflows.video_orchestrator.submit_video_scenes",
            return_value=submitted_job,
        ) as submit, patch(
            "app.workflows.video_orchestrator.refresh_video_job"
        ) as refresh:
            advanced = client.post(f"/api/workflow/jobs/{job_id}/advance")
        assert advanced.status_code == 200
        assert advanced.json()["next_action"] == "refresh"
        submit.assert_called_once_with(job_id)
        refresh.assert_not_called()

        completed_job = job_store.get_job(job_id)
        completed_job.status = VideoJobStatus.COMPLETED
        completed_job.progress = 100
        job_store.update_job(completed_job)
        with patch(
            "app.workflows.video_orchestrator.submit_video_scenes"
        ) as submit, patch(
            "app.workflows.video_orchestrator.refresh_video_job"
        ) as refresh, patch(
            "app.workflows.video_orchestrator.download_completed_scene_videos"
        ) as download, patch(
            "app.workflows.video_orchestrator.compose_ai_video_job"
        ) as compose:
            completed = client.post(f"/api/workflow/jobs/{job_id}/advance")
        assert completed.status_code == 200
        assert completed.json()["next_action"] == "completed"
        assert completed.json()["is_terminal"] is True
        submit.assert_not_called()
        refresh.assert_not_called()
        download.assert_not_called()
        compose.assert_not_called()
    finally:
        settings.s3_bucket_name = original_bucket
        settings.bedrock_video_model_id = original_video_model
        job_store.JOB_STORE_DIRECTORY = original_directory
        shutil.rmtree(temporary_directory, ignore_errors=True)


if __name__ == "__main__":
    test_health()
    test_local_vite_origin_is_allowed_by_cors()
    test_config_status_contains_only_safe_fields()
    test_plan_video_with_mock_planner()
    test_demo_render_with_mock_planner()
    test_demo_render_rejects_real_mode()
    test_job_api_without_aws()
    test_workflow_api_without_aws()
    print("API tests: SUCCESS")
