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
    get_overlay_text_layout,
    probe_stream_types,
    probe_video_duration,
    wrap_overlay_text,
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
            assert set(probe_stream_types(clip)) == {"video", "audio"}
            clips.append(clip)

        final_video = concat_scene_clips(clips, temporary_directory / "final.mp4")
        assert final_video.is_file()
        assert final_video.stat().st_size > 0
        assert abs(probe_video_duration(final_video) - 2.0) < 0.3
        assert set(probe_stream_types(final_video)) == {"video", "audio"}
    finally:
        shutil.rmtree(temporary_directory, ignore_errors=True)


def test_overlay_layout_wraps_safely_for_all_aspect_ratios() -> None:
    overlay = (
        "Tired of paying too much for tools that should make everyday work simpler?"
    )
    expected_widths = {"9:16": 720, "16:9": 1280, "1:1": 720}
    wrapped_lines: dict[str, list[str]] = {}

    for aspect_ratio, frame_width in expected_widths.items():
        layout = get_overlay_text_layout(aspect_ratio)
        lines = wrap_overlay_text(overlay, aspect_ratio).splitlines()
        wrapped_lines[aspect_ratio] = lines
        assert lines
        assert all(len(line) <= layout.wrap_width for line in lines)
        estimated_widest_line = (
            max(len(line) for line in lines) * layout.font_size * 0.62
        )
        estimated_box_width = estimated_widest_line + (2 * layout.box_border_width)
        assert estimated_box_width <= frame_width - (2 * layout.horizontal_margin)
        assert layout.horizontal_margin >= frame_width * 0.10

    assert get_overlay_text_layout("9:16").font_size == 40
    assert get_overlay_text_layout("1:1").font_size == 40
    assert get_overlay_text_layout("16:9").font_size == 48
    assert get_overlay_text_layout("9:16").wrap_width < (
        get_overlay_text_layout("16:9").wrap_width
    )
    assert max(map(len, wrapped_lines["9:16"])) <= 20
    assert max(map(len, wrapped_lines["1:1"])) <= 20


if __name__ == "__main__":
    test_overlay_layout_wraps_safely_for_all_aspect_ratios()
    test_create_and_concat_mock_clips()
    print("FFmpeg composer tests: SUCCESS")
