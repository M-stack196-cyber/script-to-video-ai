import sys
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


if __name__ == "__main__":
    test_health()
    test_config_status_contains_only_safe_fields()
    test_plan_video_with_mock_planner()
    print("API tests: SUCCESS")
