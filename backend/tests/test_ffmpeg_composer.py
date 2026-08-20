import shutil
import sys
import tempfile
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.scene import Scene  # noqa: E402
from app.services.ffmpeg_composer import (  # noqa: E402
    concat_scene_clips,
    create_mock_scene_clip,
    probe_video_duration,
)


def _scene(number: int, start: float, duration: float) -> Scene:
    return Scene(
        scene_number=number,
        start_time=start,
        end_time=start + duration,
        duration=duration,
        narration=f"Narration {number}",
        visual_description="Local generated background",
        video_prompt="Local generated background",
        camera_movement="None",
        overlay_text=f"Scene {number}",
    )


def test_create_and_concat_mock_clips() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="ffmpeg-composer-"))
    try:
        clips = []
        for scene in (_scene(1, 0.0, 1.0), _scene(2, 1.0, 1.0)):
            clip = create_mock_scene_clip(
                scene, "1:1", temporary_directory / f"scene-{scene.scene_number}.mp4"
            )
            assert clip.is_file()
            assert clip.stat().st_size > 0
            assert abs(probe_video_duration(clip) - scene.duration) < 0.2
            clips.append(clip)

        final_video = concat_scene_clips(clips, temporary_directory / "final.mp4")
        assert final_video.is_file()
        assert final_video.stat().st_size > 0
        assert abs(probe_video_duration(final_video) - 2.0) < 0.3
    finally:
        shutil.rmtree(temporary_directory, ignore_errors=True)


if __name__ == "__main__":
    test_create_and_concat_mock_clips()
    print("FFmpeg composer tests: SUCCESS")
