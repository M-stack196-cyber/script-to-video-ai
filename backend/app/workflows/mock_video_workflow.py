"""End-to-end local mock video workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import settings
from app.services.ffmpeg_composer import concat_scene_clips, create_mock_scene_clip
from app.services.scene_generator import generate_scene_plan


DEMO_OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "output" / "demo"


def render_mock_video(
    script: str,
    total_duration: int,
    aspect_ratio: str,
) -> dict[str, Any]:
    """Plan and render a local demo video without calling any cloud service."""
    if not settings.use_mock_scene_planner:
        raise RuntimeError(
            "Local demo rendering requires USE_MOCK_SCENE_PLANNER=true; "
            "real generation is never switched to mock mode automatically"
        )

    scene_plan = generate_scene_plan(script, total_duration, aspect_ratio)
    job_id = uuid4().hex
    job_directory = DEMO_OUTPUT_ROOT / job_id
    job_directory.mkdir(parents=True, exist_ok=False)

    clip_paths: list[Path] = []
    for scene in scene_plan.scenes:
        clip_path = job_directory / f"scene-{scene.scene_number:03d}.mp4"
        create_mock_scene_clip(scene, scene_plan.aspect_ratio, clip_path)
        clip_paths.append(clip_path)

    final_path = concat_scene_clips(clip_paths, job_directory / "final.mp4")
    return {
        "job_id": job_id,
        "mode": "mock",
        "final_video_path": str(final_path),
        "scene_count": len(scene_plan.scenes),
        "total_duration": scene_plan.total_duration,
        "aspect_ratio": scene_plan.aspect_ratio,
        "scenes": scene_plan.scenes,
    }
