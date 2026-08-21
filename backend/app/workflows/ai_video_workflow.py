"""Persistent orchestration for multi-scene AI video generation."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.config import settings
from app.providers.narration import get_narration_provider
from app.schemas.job import SceneJob, SceneJobStatus, VideoJob, VideoJobStatus
from app.services.job_store import create_job, get_job, update_job
from app.services.media_paths import (
    final_video_path,
    output_relative_path,
    output_public_url,
    resolve_output_path,
    scene_audio_path,
    scene_composed_path,
    scene_normalized_video_path,
    scene_video_path,
)
from app.services.production_composer import (
    concat_production_scenes,
    generate_narration,
    mux_scene_narration,
    normalize_video_clip,
)
from app.services.s3_video_service import (
    download_s3_video,
    find_generated_video_object,
)
from app.services.scene_generator import generate_scene_plan
from app.services.video_generator import (
    get_video_generation_status,
    start_video_generation,
)


def _video_progress(job: VideoJob) -> int:
    if not job.scenes:
        return 0
    completed = sum(scene.status == SceneJobStatus.COMPLETED for scene in job.scenes)
    return round(completed * 100 / len(job.scenes))


def create_ai_video_job(script: str, duration: int, aspect_ratio: str) -> VideoJob:
    job = VideoJob(
        job_id=uuid4().hex,
        status=VideoJobStatus.PLANNING,
        progress=0,
        message="Planning video scenes",
        mode="ai",
        script=script,
        duration=duration,
        aspect_ratio=aspect_ratio,
    )
    create_job(job)
    try:
        plan = generate_scene_plan(script, duration, aspect_ratio)
    except Exception as exc:
        job.status = VideoJobStatus.FAILED
        job.message = "Scene planning failed"
        job.error = str(exc)
        update_job(job)
        raise

    job.scenes = [
        SceneJob(
            scene_number=scene.scene_number,
            prompt=scene.video_prompt,
            duration=scene.duration,
            narration=scene.narration,
            overlay_text=scene.overlay_text,
        )
        for scene in plan.scenes
    ]
    job.status = VideoJobStatus.QUEUED
    job.message = f"Planned {len(job.scenes)} scenes; ready to submit video generation"
    return update_job(job)


def submit_video_scenes(job_id: str) -> VideoJob:
    if not settings.s3_bucket_name.strip():
        raise RuntimeError("S3_BUCKET_NAME is required to submit AI video scenes")

    job = get_job(job_id)
    if job.mode != "ai":
        raise ValueError("Only AI jobs can submit Nova Reel scenes")
    if job.status == VideoJobStatus.FAILED:
        raise ValueError("A failed job cannot submit video scenes")

    job.status = VideoJobStatus.GENERATING_VIDEO
    job.message = "Submitting video scenes"
    update_job(job)

    for scene in job.scenes:
        if scene.status != SceneJobStatus.QUEUED:
            continue
        try:
            scene.invocation_arn = start_video_generation(scene.prompt)
            scene.status = SceneJobStatus.SUBMITTED
            scene.error = None
            job.message = f"Submitted scene {scene.scene_number} of {len(job.scenes)}"
            update_job(job)
        except Exception as exc:
            scene.status = SceneJobStatus.FAILED
            scene.error = str(exc)
            job.status = VideoJobStatus.FAILED
            job.error = f"Scene {scene.scene_number} submission failed: {exc}"
            job.message = "Video scene submission failed"
            job.progress = _video_progress(job)
            return update_job(job)

    job.progress = _video_progress(job)
    job.message = f"Submitted {len(job.scenes)} video scenes"
    return update_job(job)


def _normalize_status(value: Any) -> SceneJobStatus | None:
    normalized = str(value or "").replace("_", "").replace("-", "").lower()
    return {
        "inprogress": SceneJobStatus.IN_PROGRESS,
        "completed": SceneJobStatus.COMPLETED,
        "failed": SceneJobStatus.FAILED,
    }.get(normalized)


def _extract_output_s3_uri(response: dict[str, Any]) -> str | None:
    for key in ("outputS3Uri", "output_s3_uri", "s3Uri"):
        value = response.get(key)
        if isinstance(value, str) and value:
            return value
    output_config = response.get("outputDataConfig")
    if isinstance(output_config, dict):
        s3_config = output_config.get("s3OutputDataConfig")
        if isinstance(s3_config, dict):
            value = s3_config.get("s3Uri")
            if isinstance(value, str) and value:
                return value
    return None


def refresh_video_job(job_id: str) -> VideoJob:
    job = get_job(job_id)
    if job.mode != "ai":
        raise ValueError("Only AI jobs can refresh Nova Reel scene status")

    refreshable = {SceneJobStatus.SUBMITTED, SceneJobStatus.IN_PROGRESS}
    for scene in job.scenes:
        if scene.status not in refreshable or not scene.invocation_arn:
            continue
        response = get_video_generation_status(scene.invocation_arn)
        normalized = _normalize_status(response.get("status"))
        if normalized is None:
            continue
        scene.status = normalized
        if normalized == SceneJobStatus.COMPLETED:
            scene.output_s3_uri = _extract_output_s3_uri(response)
            scene.error = None
        elif normalized == SceneJobStatus.FAILED:
            error = response.get("failureMessage") or response.get("error")
            scene.error = str(error or "Nova Reel generation failed")

    job.progress = _video_progress(job)
    failed = [scene for scene in job.scenes if scene.status == SceneJobStatus.FAILED]
    if failed:
        job.status = VideoJobStatus.FAILED
        job.error = failed[0].error or f"Scene {failed[0].scene_number} failed"
        job.message = "One or more video scenes failed"
    elif job.scenes and all(
        scene.status == SceneJobStatus.COMPLETED for scene in job.scenes
    ):
        job.status = VideoJobStatus.VIDEO_READY
        job.error = None
        job.message = "All video scenes are ready"
    else:
        job.status = VideoJobStatus.GENERATING_VIDEO
        job.message = f"Video generation is {job.progress}% complete"
    return update_job(job)


def download_completed_scene_videos(job_id: str) -> VideoJob:
    job = get_job(job_id)
    if job.mode != "ai":
        raise ValueError("Only AI jobs can download generated video scenes")
    if job.status != VideoJobStatus.VIDEO_READY:
        raise ValueError("AI scene videos can only be downloaded when the job is video_ready")
    if not job.scenes or any(
        scene.status != SceneJobStatus.COMPLETED for scene in job.scenes
    ):
        raise ValueError("All scenes must be completed before downloading video clips")
    missing_outputs = [
        scene.scene_number for scene in job.scenes if not scene.output_s3_uri
    ]
    if missing_outputs:
        numbers = ", ".join(str(number) for number in missing_outputs)
        raise ValueError(f"Completed scenes are missing S3 output URIs: {numbers}")

    for scene in job.scenes:
        if scene.local_video_path:
            try:
                existing_path = resolve_output_path(scene.local_video_path)
            except ValueError:
                existing_path = None
            if (
                existing_path is not None
                and existing_path.is_file()
                and existing_path.stat().st_size > 0
            ):
                scene.video_downloaded = True
                continue

        destination = scene_video_path(job.job_id, scene.scene_number)
        try:
            generated_uri = find_generated_video_object(scene.output_s3_uri or "")
            downloaded_path = download_s3_video(generated_uri, destination)
            scene.local_video_path = output_relative_path(downloaded_path)
            scene.video_downloaded = True
            scene.error = None
            job.message = f"Downloaded scene {scene.scene_number} of {len(job.scenes)}"
            update_job(job)
        except Exception as exc:
            scene.video_downloaded = False
            scene.error = str(exc)
            job.status = VideoJobStatus.FAILED
            job.error = f"Scene {scene.scene_number} download failed: {exc}"
            job.message = "AI video scene download failed"
            update_job(job)
            if isinstance(exc, RuntimeError):
                raise
            raise RuntimeError(str(exc)) from exc

    job.status = VideoJobStatus.VIDEO_READY
    job.error = None
    job.message = "All AI scene clips are downloaded locally"
    return update_job(job)


def compose_ai_video_job(job_id: str) -> VideoJob:
    job = get_job(job_id)
    if job.mode != "ai":
        raise ValueError("Only AI jobs can be composed by the production workflow")
    if job.status != VideoJobStatus.VIDEO_READY:
        raise ValueError("AI video composition requires a video_ready job")
    if not job.scenes or any(
        scene.status != SceneJobStatus.COMPLETED for scene in job.scenes
    ):
        raise ValueError("All scenes must be completed before composition")
    if any(not scene.video_downloaded for scene in job.scenes):
        raise ValueError("All scene videos must be downloaded before composition")
    if any(scene.duration is None or scene.duration <= 0 for scene in job.scenes):
        raise ValueError("Every scene requires a positive duration before composition")
    if any(not (scene.narration or "").strip() for scene in job.scenes):
        raise ValueError("Every scene requires narration before composition")

    provider_name = settings.narration_provider.strip().lower()
    job.narration_provider = provider_name
    job.status = VideoJobStatus.GENERATING_AUDIO
    job.message = f"Generating narration with {provider_name} provider"
    job.error = None
    update_job(job)

    ordered_scenes = sorted(job.scenes, key=lambda item: item.scene_number)
    source_paths = {}
    narration_paths = {}
    try:
        provider = get_narration_provider()
        for scene in ordered_scenes:
            if not scene.local_video_path:
                raise RuntimeError(
                    f"Downloaded video path is missing for scene {scene.scene_number}"
                )
            source = resolve_output_path(scene.local_video_path)
            if not source.is_file() or source.stat().st_size <= 0:
                raise RuntimeError(
                    f"Downloaded video is missing or empty for scene {scene.scene_number}"
                )
            duration = float(scene.duration or 0)
            source_paths[scene.scene_number] = source
            narration_paths[scene.scene_number] = generate_narration(
                scene.narration or "",
                scene_audio_path(job.job_id, scene.scene_number),
                duration=duration,
                provider=provider,
            )
            job.message = (
                f"Generated narration for scene {scene.scene_number} "
                f"of {len(job.scenes)}"
            )
            update_job(job)

        job.status = VideoJobStatus.COMPOSING
        job.message = "Composing final video"
        update_job(job)

        composed_paths = []
        for scene in ordered_scenes:
            duration = float(scene.duration or 0)
            normalized = normalize_video_clip(
                source_paths[scene.scene_number],
                scene_normalized_video_path(job.job_id, scene.scene_number),
                duration,
                job.aspect_ratio,
            )
            composed = mux_scene_narration(
                normalized,
                narration_paths[scene.scene_number],
                scene_composed_path(job.job_id, scene.scene_number),
                duration,
            )
            composed_paths.append(composed)
            job.message = f"Composed scene {scene.scene_number} of {len(job.scenes)}"
            update_job(job)

        final_path = concat_production_scenes(
            composed_paths,
            final_video_path(job.job_id),
        )
        relative_final_path = output_relative_path(final_path)
    except Exception as exc:
        failed_during_audio = job.status == VideoJobStatus.GENERATING_AUDIO
        job.status = VideoJobStatus.FAILED
        job.message = (
            f"Narration generation with {provider_name} failed"
            if failed_during_audio
            else "Video composition failed"
        )
        job.error = str(exc)
        update_job(job)
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError(str(exc)) from exc

    job.final_video_url = output_public_url(relative_final_path)
    job.status = VideoJobStatus.COMPLETED
    job.progress = 100
    job.message = "Video completed"
    job.error = None
    return update_job(job)
