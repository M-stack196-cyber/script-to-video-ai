"""Local production-media normalization, narration, and composition helpers."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.providers.narration import (
    LocalEspeakNarrationProvider,
    NarrationProvider,
    get_narration_provider,
)


VIDEO_DIMENSIONS = {
    "9:16": (720, 1280),
    "16:9": (1280, 720),
    "1:1": (720, 720),
}


def check_media_tools() -> None:
    missing = [
        executable
        for executable in ("ffmpeg", "ffprobe")
        if shutil.which(executable) is None
    ]
    if missing:
        raise RuntimeError(
            "Production composition requires installed command(s): "
            + ", ".join(missing)
        )


def _run(command: list[str], operation: str, tool: str = "FFmpeg") -> None:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise RuntimeError(f"Could not start {tool} while {operation}: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
        raise RuntimeError(f"{tool} failed while {operation}: {detail}")


def _require_nonempty_file(path: Path, description: str) -> None:
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError(f"{description} is missing or empty: {path}")


def _partial_path(destination: Path, suffix: str) -> Path:
    return destination.parent / f".{destination.name}.{uuid4().hex}.part{suffix}"


def probe_media(path: str | Path) -> dict[str, Any]:
    check_media_tools()
    media_path = Path(path)
    _require_nonempty_file(media_path, "Media file")
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(media_path),
    ]
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
    except OSError as exc:
        raise RuntimeError(f"Could not start FFprobe: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "unknown error"
        raise RuntimeError(f"FFprobe failed while inspecting media: {detail}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("FFprobe returned invalid JSON") from exc

    streams = payload.get("streams", [])
    video_stream = next(
        (stream for stream in streams if stream.get("codec_type") == "video"), None
    )
    has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
    duration_value = payload.get("format", {}).get("duration")
    if duration_value is None and video_stream:
        duration_value = video_stream.get("duration")
    try:
        duration = float(duration_value)
    except (TypeError, ValueError):
        duration = 0.0
    return {
        "duration": duration,
        "width": int(video_stream.get("width", 0)) if video_stream else 0,
        "height": int(video_stream.get("height", 0)) if video_stream else 0,
        "video_codec": video_stream.get("codec_name") if video_stream else None,
        "has_video": video_stream is not None,
        "has_audio": has_audio,
    }


def normalize_video_clip(
    source_path: str | Path,
    destination_path: str | Path,
    duration: float,
    aspect_ratio: str,
) -> Path:
    check_media_tools()
    if aspect_ratio not in VIDEO_DIMENSIONS:
        raise ValueError(f"Unsupported aspect ratio: {aspect_ratio}")
    if duration <= 0:
        raise ValueError("Scene duration must be greater than zero")
    source = Path(source_path)
    _require_nonempty_file(source, "Source video")
    destination = Path(destination_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = _partial_path(destination, ".mp4")
    width, height = VIDEO_DIMENSIONS[aspect_ratio]
    duration_text = f"{duration:.6f}"
    video_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps=24,"
        f"tpad=stop_mode=clone:stop_duration={duration_text},"
        f"trim=duration={duration_text},setpts=PTS-STARTPTS"
    )
    try:
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-vf",
            video_filter,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "24",
            "-f",
            "mp4",
            str(partial),
        ]
        _run(command, "normalizing a scene video")
        _require_nonempty_file(partial, "Normalized video")
        partial.replace(destination)
    finally:
        partial.unlink(missing_ok=True)
    return destination


def generate_narration(
    narration: str,
    destination_wav: Path,
    duration: float | None = None,
    provider: NarrationProvider | None = None,
) -> Path:
    selected_provider = provider or get_narration_provider()
    return selected_provider.synthesize(
        narration,
        Path(destination_wav),
        duration=duration,
    )


def generate_local_narration(narration: str, destination_wav: Path) -> Path:
    """Backward-compatible explicit local narration helper."""
    return generate_narration(
        narration,
        destination_wav,
        provider=LocalEspeakNarrationProvider(),
    )


def mux_scene_narration(
    video_path: str | Path,
    narration_wav: str | Path,
    destination_path: str | Path,
    duration: float,
) -> Path:
    check_media_tools()
    if duration <= 0:
        raise ValueError("Scene duration must be greater than zero")
    video = Path(video_path)
    narration = Path(narration_wav)
    _require_nonempty_file(video, "Normalized video")
    _require_nonempty_file(narration, "Narration WAV")
    destination = Path(destination_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = _partial_path(destination, ".mp4")
    duration_text = f"{duration:.6f}"
    try:
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video),
            "-i",
            str(narration),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-af",
            f"apad,atrim=0:{duration_text},asetpts=N/SR/TB",
            "-t",
            duration_text,
            "-c:v",
            "copy",
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
            "-f",
            "mp4",
            str(partial),
        ]
        _run(command, "muxing scene narration")
        _require_nonempty_file(partial, "Composed scene video")
        partial.replace(destination)
    finally:
        partial.unlink(missing_ok=True)
    return destination


def _concat_entry(path: Path) -> str:
    escaped = str(path.resolve()).replace("'", "'\\''")
    return f"file '{escaped}'\n"


def concat_production_scenes(
    scene_paths: list[str | Path], destination_path: str | Path
) -> Path:
    check_media_tools()
    if not scene_paths:
        raise ValueError("At least one composed scene is required")
    scenes = [Path(path) for path in scene_paths]
    for scene in scenes:
        _require_nonempty_file(scene, "Composed scene video")
    destination = Path(destination_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = destination.parent / f".{destination.name}.{uuid4().hex}.concat.txt"
    partial = _partial_path(destination, ".mp4")
    try:
        manifest.write_text("".join(_concat_entry(scene) for scene in scenes), encoding="utf-8")
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
            "-f",
            "mp4",
            str(partial),
        ]
        _run(command, "concatenating production scenes")
        _require_nonempty_file(partial, "Final video")
        partial.replace(destination)
    except OSError as exc:
        raise RuntimeError(f"Could not create the production concat manifest: {exc}") from exc
    finally:
        manifest.unlink(missing_ok=True)
        partial.unlink(missing_ok=True)
    return destination
