import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.production_composer import (  # noqa: E402
    concat_production_scenes,
    generate_local_narration,
    mux_scene_narration,
    normalize_video_clip,
    probe_media,
)


def _synthetic_video(destination: Path, duration: float = 0.6) -> Path:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=s=320x180:r=24:d={duration}",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(destination),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr)
    return destination


def test_probe_and_normalize_aspect_ratios() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="production-normalize-"))
    try:
        source = _synthetic_video(temporary_directory / "source.mp4")
        source_info = probe_media(source)
        assert source_info["has_video"] is True
        assert source_info["width"] == 320
        assert source_info["height"] == 180

        expected_dimensions = {
            "9:16": (720, 1280),
            "16:9": (1280, 720),
            "1:1": (720, 720),
        }
        for index, (aspect_ratio, dimensions) in enumerate(
            expected_dimensions.items(), start=1
        ):
            normalized = normalize_video_clip(
                source,
                temporary_directory / f"normalized-{index}.mp4",
                0.75,
                aspect_ratio,
            )
            info = probe_media(normalized)
            assert normalized.stat().st_size > 0
            assert (info["width"], info["height"]) == dimensions
            assert info["video_codec"] == "h264"
            assert info["has_audio"] is False
            assert abs(info["duration"] - 0.75) < 0.15
    finally:
        shutil.rmtree(temporary_directory, ignore_errors=True)


def test_narration_mux_and_concat() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="production-compose-"))
    try:
        source = _synthetic_video(temporary_directory / "source.mp4", duration=0.5)
        composed_scenes = []
        for number in (1, 2):
            normalized = normalize_video_clip(
                source,
                temporary_directory / f"normalized-{number}.mp4",
                0.7,
                "16:9",
            )
            narration = generate_local_narration(
                f"This is local narration for scene {number}.",
                temporary_directory / f"narration-{number}.wav",
            )
            assert narration.is_file() and narration.stat().st_size > 0
            composed = mux_scene_narration(
                normalized,
                narration,
                temporary_directory / f"composed-{number}.mp4",
                0.7,
            )
            info = probe_media(composed)
            assert info["has_video"] is True
            assert info["has_audio"] is True
            assert abs(info["duration"] - 0.7) < 0.15
            composed_scenes.append(composed)

        final_video = concat_production_scenes(
            composed_scenes, temporary_directory / "final.mp4"
        )
        final_info = probe_media(final_video)
        assert final_video.stat().st_size > 0
        assert final_info["has_video"] is True
        assert final_info["has_audio"] is True
        assert abs(final_info["duration"] - 1.4) < 0.25
    finally:
        shutil.rmtree(temporary_directory, ignore_errors=True)


if __name__ == "__main__":
    test_probe_and_normalize_aspect_ratios()
    test_narration_mux_and_concat()
    print("Production composer tests: SUCCESS")
