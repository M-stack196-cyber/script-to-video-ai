"""Single-step orchestration over the persistent AI video job workflow."""

from __future__ import annotations

from app.schemas.job import (
    SceneJobStatus,
    VideoJob,
    VideoJobNextAction,
    VideoJobStatus,
    VideoJobWorkflowState,
    VideoWorkflowStage,
)
from app.services.job_store import get_job
from app.workflows.ai_video_workflow import (
    compose_ai_video_job,
    create_ai_video_job,
    download_completed_scene_videos,
    refresh_video_job,
    submit_video_scenes,
)


def _all_scenes_completed(job: VideoJob) -> bool:
    return bool(job.scenes) and all(
        scene.status == SceneJobStatus.COMPLETED for scene in job.scenes
    )


def _all_clips_downloaded(job: VideoJob) -> bool:
    return bool(job.scenes) and all(
        scene.video_downloaded and bool(scene.local_video_path)
        for scene in job.scenes
    )


def determine_next_action(job: VideoJob) -> VideoJobNextAction:
    if job.status == VideoJobStatus.QUEUED:
        return (
            VideoJobNextAction.SUBMIT_VIDEO
            if job.mode == "ai" and bool(job.scenes)
            else VideoJobNextAction.NONE
        )
    if job.status == VideoJobStatus.GENERATING_VIDEO:
        return (
            VideoJobNextAction.REFRESH
            if job.mode == "ai" and bool(job.scenes)
            else VideoJobNextAction.NONE
        )
    if job.status == VideoJobStatus.VIDEO_READY:
        if job.mode != "ai" or not _all_scenes_completed(job):
            return VideoJobNextAction.NONE
        if not _all_clips_downloaded(job):
            return VideoJobNextAction.DOWNLOAD_VIDEO
        return VideoJobNextAction.COMPOSE
    if job.status == VideoJobStatus.COMPLETED:
        return VideoJobNextAction.COMPLETED
    return VideoJobNextAction.NONE


def _determine_stage(job: VideoJob, action: VideoJobNextAction) -> VideoWorkflowStage:
    if job.status == VideoJobStatus.PLANNING:
        return VideoWorkflowStage.PLANNING
    if job.status == VideoJobStatus.QUEUED:
        return VideoWorkflowStage.WAITING_TO_SUBMIT
    if job.status == VideoJobStatus.GENERATING_VIDEO:
        return VideoWorkflowStage.GENERATING_VIDEO
    if job.status == VideoJobStatus.GENERATING_AUDIO:
        return VideoWorkflowStage.GENERATING_AUDIO
    if job.status == VideoJobStatus.COMPOSING:
        return VideoWorkflowStage.COMPOSING
    if job.status == VideoJobStatus.COMPLETED:
        return VideoWorkflowStage.COMPLETED
    if job.status == VideoJobStatus.FAILED:
        return VideoWorkflowStage.FAILED
    if action == VideoJobNextAction.DOWNLOAD_VIDEO:
        return VideoWorkflowStage.DOWNLOADING
    return VideoWorkflowStage.COMPOSING


def _workflow_state(job: VideoJob) -> VideoJobWorkflowState:
    action = determine_next_action(job)
    terminal = job.status in {VideoJobStatus.COMPLETED, VideoJobStatus.FAILED}
    return VideoJobWorkflowState(
        job=job,
        next_action=action,
        stage=_determine_stage(job, action),
        can_submit_video=action == VideoJobNextAction.SUBMIT_VIDEO,
        can_refresh=action == VideoJobNextAction.REFRESH,
        can_download_video=action == VideoJobNextAction.DOWNLOAD_VIDEO,
        can_compose=action == VideoJobNextAction.COMPOSE,
        is_terminal=terminal,
    )


def get_job_workflow_state(job_id: str) -> VideoJobWorkflowState:
    return _workflow_state(get_job(job_id))


def create_video_workflow_job(
    script: str,
    duration: int,
    aspect_ratio: str,
) -> VideoJobWorkflowState:
    job = create_ai_video_job(script, duration, aspect_ratio)
    return _workflow_state(job)


def advance_video_job(job_id: str) -> VideoJobWorkflowState:
    current = get_job_workflow_state(job_id)
    action = current.next_action
    if action == VideoJobNextAction.SUBMIT_VIDEO:
        updated = submit_video_scenes(job_id)
    elif action == VideoJobNextAction.REFRESH:
        updated = refresh_video_job(job_id)
    elif action == VideoJobNextAction.DOWNLOAD_VIDEO:
        updated = download_completed_scene_videos(job_id)
    elif action == VideoJobNextAction.COMPOSE:
        updated = compose_ai_video_job(job_id)
    else:
        updated = current.job
    return _workflow_state(updated)
