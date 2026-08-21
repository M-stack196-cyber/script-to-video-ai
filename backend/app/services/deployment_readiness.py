"""Side-effect-free deployment readiness checks.

These checks inspect configuration and local executable availability only. They
must never contact AWS or imply that local files are durable in production.
"""

from __future__ import annotations

from app.config import settings
from app.providers.nova_sonic import (
    standard_aws_credentials_detected,
)
from app.schemas.api import DeploymentReadinessResponse


def get_deployment_readiness() -> DeploymentReadinessResponse:
    blockers: list[str] = []

    def block(message: str) -> None:
        if message not in blockers:
            blockers.append(message)

    production = settings.is_production
    credentials_ready = standard_aws_credentials_detected()
    public_url_ready = bool(settings.public_base_url.strip())
    cors_ready = bool(settings.cors_origin_list)
    frontend_ready = cors_ready and (not production or public_url_ready)
    if not cors_ready:
        block("CORS origins are not configured")
    if production and not public_url_ready:
        block("PUBLIC_BASE_URL is not configured")

    text_model_ready = bool(settings.bedrock_text_model_id.strip())
    scene_planner_ready = (
        settings.use_mock_scene_planner and not production
    ) or (text_model_ready and credentials_ready)
    if not scene_planner_ready:
        if not text_model_ready:
            block("Bedrock text model is not configured")
        elif not credentials_ready:
            block("Standard AWS credentials are not detected")

    video_model_ready = bool(settings.bedrock_video_model_id.strip())
    s3_ready = bool(settings.s3_bucket_name.strip())
    video_generation_ready = video_model_ready and s3_ready and credentials_ready
    if not video_model_ready:
        block("Bedrock video model is not configured")
    if not s3_ready:
        block("S3 bucket is not configured")
    if video_model_ready and s3_ready and not credentials_ready:
        block("Standard AWS credentials are not detected")

    durable_job_storage_ready = settings.production_storage_ready
    if production and not durable_job_storage_ready:
        if settings.normalized_job_store_provider == "local":
            block("Local job storage is not durable in production")
        else:
            block("Production durable job storage is not implemented")

    media_storage_ready = settings.local_media_enabled
    if production and not media_storage_ready:
        block("Production durable media storage is not implemented")

    provider = settings.narration_provider.strip().lower()
    if provider == "local":
        # Readiness is configuration-only. Executable probing belongs to the
        # local render operation, where the composer already reports failures.
        narration_ready = settings.local_media_enabled
    elif provider == "nova-sonic":
        # The provider foundation deliberately does not implement its streaming
        # exchange yet, so production readiness must not claim otherwise.
        narration_ready = False
        if not settings.bedrock_audio_model_id.strip():
            block("Bedrock audio model is not configured")
        if not credentials_ready:
            block("Standard AWS credentials are not detected")
        block("Nova Sonic streaming is not enabled")
    else:
        narration_ready = False
        block("Narration provider is not supported")

    local_demo_available = (
        settings.local_media_enabled
        and settings.use_mock_scene_planner
        and provider == "local"
    )

    ready = all(
        (
            frontend_ready,
            scene_planner_ready,
            video_generation_ready,
            durable_job_storage_ready,
            media_storage_ready,
            narration_ready,
        )
    )
    return DeploymentReadinessResponse(
        ready=ready,
        app_env=settings.normalized_app_env,
        frontend_ready=frontend_ready,
        scene_planner_ready=scene_planner_ready,
        video_generation_ready=video_generation_ready,
        durable_job_storage_ready=durable_job_storage_ready,
        media_storage_ready=media_storage_ready,
        narration_ready=narration_ready,
        local_demo_available=local_demo_available,
        blockers=blockers,
    )
