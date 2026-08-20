import sys
import shutil
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_config_status_contains_only_safe_fields() -> None:
    response = client.get("/api/config/status")

    assert response.status_code == 200
    assert set(response.json()) == {
        "text_model_configured",
        "video_model_configured",
        "audio_model_configured",
        "s3_configured",
        "mock_scene_planner",
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


if __name__ == "__main__":
    test_health()
    test_config_status_contains_only_safe_fields()
    test_plan_video_with_mock_planner()
    test_demo_render_with_mock_planner()
    test_demo_render_rejects_real_mode()
    print("API tests: SUCCESS")
