import shutil
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.services.ffmpeg_composer import probe_video_duration  # noqa: E402
from app.workflows.mock_video_workflow import render_mock_video  # noqa: E402


def test_render_mock_video() -> None:
    original_mock_setting = settings.use_mock_scene_planner
    settings.use_mock_scene_planner = True
    job_directory = None
    try:
        result = render_mock_video(
            script="A quick local demo with no cloud services.",
            total_duration=2,
            aspect_ratio="16:9",
        )
        final_video = Path(result["final_video_path"])
        job_directory = final_video.parent
        assert result["mode"] == "mock"
        assert result["scene_count"] == 1
        assert final_video.is_file()
        assert final_video.stat().st_size > 0
        assert abs(probe_video_duration(final_video) - 2.0) < 0.3
    finally:
        settings.use_mock_scene_planner = original_mock_setting
        if job_directory is not None:
            shutil.rmtree(job_directory, ignore_errors=True)


def test_render_requires_mock_setting() -> None:
    original_mock_setting = settings.use_mock_scene_planner
    settings.use_mock_scene_planner = False
    try:
        try:
            render_mock_video("No cloud fallback", 1, "1:1")
        except RuntimeError as exc:
            assert "USE_MOCK_SCENE_PLANNER=true" in str(exc)
        else:
            raise AssertionError("Expected render_mock_video to reject real mode")
    finally:
        settings.use_mock_scene_planner = original_mock_setting


if __name__ == "__main__":
    test_render_mock_video()
    test_render_requires_mock_setting()
    print("Mock video workflow tests: SUCCESS")
