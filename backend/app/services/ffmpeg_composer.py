"""Local-only FFmpeg helpers for mock/demo video rendering."""

from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path

from app.schemas.scene import Scene


VIDEO_DIMENSIONS = {
    "9:16": (720, 1280),
    "16:9": (1280, 720),
    "1:1": (720, 720),
}

REGULAR_FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
BOLD_FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")


def check_ffmpeg_available() -> None:
    """Raise a useful error unless both FFmpeg and FFprobe are installed."""
    missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if missing:
        raise RuntimeError(
            "Local demo rendering requires installed command(s): " + ", ".join(missing)
        )


def check_espeak_available() -> str:
    """Return the espeak-ng executable path or raise a clear local TTS error."""
    executable = shutil.which("espeak-ng")
    if executable is None:
        raise RuntimeError(
            "Spoken demo narration requires espeak-ng, but it was not found on PATH"
        )
    return executable


def _run(command: list[str], operation: str, tool_name: str = "FFmpeg") -> None:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise RuntimeError(f"Could not start {tool_name} while {operation}: {exc}") from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
        raise RuntimeError(f"{tool_name} failed while {operation}: {detail}")


def _escape_filter_path(path: Path) -> str:
    """Escape a path embedded in an FFmpeg filter option."""
    return str(path.resolve()).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _write_scene_text_files(scene: Scene, directory: Path, width: int) -> tuple[Path, Path]:
    scene_text_path = directory / f".scene-{scene.scene_number:03d}-label.txt"
    overlay_path = directory / f".scene-{scene.scene_number:03d}-overlay.txt"
    scene_text_path.write_text(f"SCENE {scene.scene_number}\n", encoding="utf-8")
    wrap_width = 25 if width == 720 else 38
    overlay = scene.overlay_text.strip() or scene.narration.strip() or f"Scene {scene.scene_number}"
    wrapped_overlay = "\n".join(textwrap.wrap(overlay, width=wrap_width))
    overlay_path.write_text(wrapped_overlay + "\n", encoding="utf-8")
    return scene_text_path, overlay_path


def _generate_narration_wav(scene: Scene, output_path: Path) -> Path:
    executable = check_espeak_available()
    narration = scene.narration.strip()
    if not narration:
        raise ValueError("Narration text cannot be empty when generating speech")
    command = [
        executable,
        "-w",
        str(output_path),
        "-s",
        "155",
        "-a",
        "175",
        "--",
        narration,
    ]
    _run(command, f"generating narration for scene {scene.scene_number}", "espeak-ng")
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError(
            f"espeak-ng failed to create narration audio for scene {scene.scene_number}"
        )
    return output_path


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

    for font in (REGULAR_FONT, BOLD_FONT):
        if not font.is_file():
            raise RuntimeError(f"Required demo text font was not found: {font}")

    palette = ("243b55", "4b2b63", "155e75", "713f12", "3f3f46", "14532d")
    color = palette[(scene.scene_number - 1) % len(palette)]
    video_filter = f"color=c=0x{color}:s={width}x{height}:r=24:d={duration}"
    narration_path = destination.parent / f".scene-{scene.scene_number:03d}-narration.wav"
    scene_text_path, overlay_path = _write_scene_text_files(
        scene, destination.parent, width
    )
    temporary_paths = (narration_path, scene_text_path, overlay_path)
    try:
        _generate_narration_wav(scene, narration_path)
        fade_duration = min(0.35, scene.duration / 3)
        fade_out_start = max(0.0, scene.duration - fade_duration)
        scene_font_size = max(22, round(height / 34))
        overlay_font_size = max(36, round(min(width, height) / 13))
        filter_chain = ",".join(
            [
                # Layered translucent shapes and a vignette give each palette
                # color a distinct, modern card-like composition.
                "drawbox=x=-iw/8:y=ih/8:w=iw*0.72:h=ih*0.34:color=white@0.055:t=fill",
                "drawbox=x=iw*0.58:y=ih*0.58:w=iw*0.55:h=ih*0.5:color=black@0.16:t=fill",
                "vignette=PI/5",
                (
                    f"drawtext=fontfile='{_escape_filter_path(REGULAR_FONT)}':"
                    f"textfile='{_escape_filter_path(scene_text_path)}':expansion=none:"
                    f"fontsize={scene_font_size}:fontcolor=white@0.72:"
                    "x=(w-text_w)/2:y=h*0.23"
                ),
                (
                    f"drawtext=fontfile='{_escape_filter_path(BOLD_FONT)}':"
                    f"textfile='{_escape_filter_path(overlay_path)}':expansion=none:"
                    f"fontsize={overlay_font_size}:fontcolor=white:line_spacing=12:"
                    "box=1:boxcolor=black@0.34:boxborderw=24:"
                    "x=(w-text_w)/2:y=(h-text_h)/2"
                ),
                f"fade=t=in:st=0:d={fade_duration:.3f}",
                f"fade=t=out:st={fade_out_start:.3f}:d={fade_duration:.3f}",
            ]
        )
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
            "-i",
            str(narration_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-vf",
            filter_chain,
            "-af",
            f"apad,atrim=0:{duration},asetpts=N/SR/TB",
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
            "-ar",
            "48000",
            "-ac",
            "2",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(destination),
        ]
        _run(command, f"rendering scene {scene.scene_number}")
    finally:
        for temporary_path in temporary_paths:
            temporary_path.unlink(missing_ok=True)
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


def probe_stream_types(path: str | Path) -> list[str]:
    """Return media stream codec types (for example, video and audio)."""
    check_ffmpeg_available()
    media_path = Path(path)
    if not media_path.is_file():
        raise ValueError(f"Video does not exist: {media_path}")
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type",
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
        raise RuntimeError(f"FFprobe failed while reading media streams: {detail}")
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]
