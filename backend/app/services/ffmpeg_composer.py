"""Local-only FFmpeg helpers for mock/demo video rendering."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from app.schemas.scene import Scene


VIDEO_DIMENSIONS = {
    "9:16": (720, 1280),
    "16:9": (1280, 720),
    "1:1": (720, 720),
}


def check_ffmpeg_available() -> None:
    """Raise a useful error unless both FFmpeg and FFprobe are installed."""
    missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if missing:
        raise RuntimeError(
            "Local demo rendering requires installed command(s): " + ", ".join(missing)
        )


def _run(command: list[str], operation: str) -> None:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise RuntimeError(f"Could not start FFmpeg while {operation}: {exc}") from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
        raise RuntimeError(f"FFmpeg failed while {operation}: {detail}")


def create_mock_scene_clip(
    scene: Scene,
    aspect_ratio: str,
    output_path: str | Path,
) -> Path:
    """Create a generated H.264/AAC MP4 whose duration matches the scene."""
    check_ffmpeg_available()
    if aspect_ratio not in VIDEO_DIMENSIONS:
        raise ValueError(f"Unsupported aspect ratio: {aspect_ratio}")
    if scene.duration <= 0:
        raise ValueError("Scene duration must be greater than zero")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    width, height = VIDEO_DIMENSIONS[aspect_ratio]
    duration = f"{scene.duration:.6f}"

    # A color source is broadly supported. Text is intentionally omitted so that
    # rendering does not depend on a system font or the optional drawtext filter.
    palette = ("243b55", "4b2b63", "155e75", "713f12", "3f3f46", "14532d")
    color = palette[(scene.scene_number - 1) % len(palette)]
    video_filter = f"color=c=0x{color}:s={width}x{height}:r=24:d={duration}"
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        video_filter,
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-t",
        duration,
        "-r",
        "24",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    _run(command, f"rendering scene {scene.scene_number}")
    return destination


def _concat_file_entry(path: Path) -> str:
    # FFmpeg concat demuxer quoting: end the quote, escape a quote, then reopen it.
    escaped = str(path.resolve()).replace("'", "'\\''")
    return f"file '{escaped}'\n"


def concat_scene_clips(
    clip_paths: list[str | Path],
    output_path: str | Path,
) -> Path:
    """Losslessly concatenate compatible scene MP4s into one final MP4."""
    check_ffmpeg_available()
    if not clip_paths:
        raise ValueError("At least one scene clip is required")

    clips = [Path(path) for path in clip_paths]
    missing = [str(path) for path in clips if not path.is_file()]
    if missing:
        raise ValueError("Scene clip does not exist: " + ", ".join(missing))

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = destination.parent / f".{destination.stem}-concat.txt"
    manifest.write_text("".join(_concat_file_entry(path) for path in clips), encoding="utf-8")
    try:
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(manifest),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(destination),
        ]
        _run(command, "concatenating scene clips")
    finally:
        manifest.unlink(missing_ok=True)
    return destination


def probe_video_duration(path: str | Path) -> float:
    """Return a media file's duration in seconds using FFprobe."""
    check_ffmpeg_available()
    media_path = Path(path)
    if not media_path.is_file():
        raise ValueError(f"Video does not exist: {media_path}")

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(media_path),
    ]
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
    except OSError as exc:
        raise RuntimeError(f"Could not start FFprobe: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "unknown error"
        raise RuntimeError(f"FFprobe failed while reading video duration: {detail}")
    try:
        return float(completed.stdout.strip())
    except ValueError as exc:
        raise RuntimeError("FFprobe returned an invalid video duration") from exc
