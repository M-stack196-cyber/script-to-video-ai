from typing import Any

from fastapi import FastAPI, HTTPException, Query, status

from app.config import settings
from app.schemas.api import (
    ConfigStatusResponse,
    GenerateSceneRequest,
    GenerateSceneResponse,
    VideoPlanRequest,
)
from app.schemas.scene import ScenePlan
from app.services.scene_generator import generate_scene_plan
from app.services.video_generator import (
    get_video_generation_status,
    start_video_generation,
)

app = FastAPI(
    title="Script to Video AI",
    description="AI-powered script-to-video generation workflow",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "name": "Script to Video AI",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }


@app.post("/api/video/plan", response_model=ScenePlan)
def plan_video(request: VideoPlanRequest) -> ScenePlan:
    try:
        return generate_scene_plan(
            script=request.script,
            total_duration=request.duration,
            aspect_ratio=request.aspect_ratio,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if "not configured" in str(exc).lower()
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@app.post("/api/video/generate-scene", response_model=GenerateSceneResponse)
def generate_video_scene(request: GenerateSceneRequest) -> GenerateSceneResponse:
    if not settings.s3_bucket_name.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="S3_BUCKET_NAME is required for Nova Reel generation",
        )
    if not settings.bedrock_video_model_id.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BEDROCK_VIDEO_MODEL_ID is not configured",
        )

    try:
        invocation_arn = start_video_generation(request.prompt, request.seed)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return GenerateSceneResponse(
        status="submitted",
        invocation_arn=invocation_arn,
    )


@app.get("/api/video/status")
def video_status(
    invocation_arn: str = Query(min_length=1),
) -> dict[str, Any]:
    try:
        return get_video_generation_status(invocation_arn)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.get("/api/config/status", response_model=ConfigStatusResponse)
def config_status() -> ConfigStatusResponse:
    return ConfigStatusResponse(
        text_model_configured=bool(settings.bedrock_text_model_id.strip()),
        video_model_configured=bool(settings.bedrock_video_model_id.strip()),
        audio_model_configured=bool(settings.bedrock_audio_model_id.strip()),
        s3_configured=bool(settings.s3_bucket_name.strip()),
        mock_scene_planner=settings.use_mock_scene_planner,
    )
