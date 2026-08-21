from typing import Any

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.schemas.api import (
    ConfigStatusResponse,
    CreateVideoJobRequest,
    GenerateSceneRequest,
    GenerateSceneResponse,
    MockRenderResponse,
    VideoPlanRequest,
)
from app.schemas.job import VideoJob, VideoJobNextAction, VideoJobWorkflowState
from app.schemas.scene import ScenePlan
from app.providers.nova_sonic import (
    nova_sonic_sdk_available,
    standard_aws_credentials_detected,
)
from app.services.scene_generator import generate_scene_plan
from app.services.job_store import JobNotFoundError, get_job, list_jobs
from app.services.video_generator import (
    get_video_generation_status,
    start_video_generation,
)
from app.workflows.mock_video_workflow import DEMO_OUTPUT_ROOT, render_mock_video
from app.workflows.video_orchestrator import (
    advance_video_job,
    create_video_workflow_job,
    get_job_workflow_state,
)
from app.workflows.ai_video_workflow import (
    compose_ai_video_job,
    create_ai_video_job,
    download_completed_scene_videos,
    refresh_video_job,
    submit_video_scenes,
)


BACKEND_ROOT = DEMO_OUTPUT_ROOT.parents[1]
OUTPUT_ROOT = BACKEND_ROOT / "output"
STATIC_ROOT = BACKEND_ROOT / "static"
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Script to Video AI",
    description="AI-powered script-to-video generation workflow",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
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


@app.get("/demo", include_in_schema=False)
def demo_page() -> FileResponse:
    return FileResponse(STATIC_ROOT / "demo.html")


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


@app.post("/api/video/demo-render", response_model=MockRenderResponse)
def demo_render(request: VideoPlanRequest) -> MockRenderResponse:
    if not settings.use_mock_scene_planner:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local demo rendering requires USE_MOCK_SCENE_PLANNER=true",
        )
    try:
        result = render_mock_video(
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return MockRenderResponse(
        job_id=result["job_id"],
        mode="mock",
        video_url=f'/output/demo/{result["job_id"]}/final.mp4',
        scene_count=result["scene_count"],
        total_duration=result["total_duration"],
        aspect_ratio=result["aspect_ratio"],
    )


@app.post("/api/jobs", response_model=VideoJob)
def create_video_job(request: CreateVideoJobRequest) -> VideoJob:
    try:
        return create_ai_video_job(
            script=request.script,
            duration=request.duration,
            aspect_ratio=request.aspect_ratio,
        )
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


@app.post("/api/workflow/jobs", response_model=VideoJobWorkflowState)
def create_workflow_video_job(request: VideoPlanRequest) -> VideoJobWorkflowState:
    try:
        return create_video_workflow_job(
            script=request.script,
            duration=request.duration,
            aspect_ratio=request.aspect_ratio,
        )
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


@app.get(
    "/api/workflow/jobs/{job_id}",
    response_model=VideoJobWorkflowState,
)
def workflow_video_job(job_id: str) -> VideoJobWorkflowState:
    try:
        return get_job_workflow_state(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@app.post(
    "/api/workflow/jobs/{job_id}/advance",
    response_model=VideoJobWorkflowState,
)
def advance_workflow_video_job(job_id: str) -> VideoJobWorkflowState:
    try:
        current = get_job_workflow_state(job_id)
        if (
            current.next_action == VideoJobNextAction.SUBMIT_VIDEO
            and not settings.s3_bucket_name.strip()
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="S3_BUCKET_NAME is required to submit AI video scenes",
            )
        if (
            current.next_action == VideoJobNextAction.SUBMIT_VIDEO
            and not settings.bedrock_video_model_id.strip()
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="BEDROCK_VIDEO_MODEL_ID is required to submit AI video scenes",
            )
        return advance_video_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        failure_status = (
            status.HTTP_500_INTERNAL_SERVER_ERROR
            if "composition" in str(exc).lower()
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=failure_status, detail=str(exc)) from exc


@app.get("/api/jobs", response_model=list[VideoJob])
def recent_video_jobs(limit: int = Query(default=20, ge=1, le=100)) -> list[VideoJob]:
    return list_jobs(limit=limit)


@app.get("/api/jobs/{job_id}", response_model=VideoJob)
def video_job(job_id: str) -> VideoJob:
    try:
        return get_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@app.post("/api/jobs/{job_id}/submit-video", response_model=VideoJob)
def submit_video_job(job_id: str) -> VideoJob:
    if not settings.s3_bucket_name.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="S3_BUCKET_NAME is required to submit AI video scenes",
        )
    try:
        return submit_video_scenes(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.post("/api/jobs/{job_id}/refresh", response_model=VideoJob)
def refresh_video_job_status(job_id: str) -> VideoJob:
    try:
        return refresh_video_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.post("/api/jobs/{job_id}/download-video", response_model=VideoJob)
def download_video_job(job_id: str) -> VideoJob:
    try:
        return download_completed_scene_videos(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.post("/api/jobs/{job_id}/compose", response_model=VideoJob)
def compose_video_job(job_id: str) -> VideoJob:
    try:
        return compose_ai_video_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


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
        narration_provider=settings.narration_provider,
        nova_sonic_sdk_available=nova_sonic_sdk_available(),
        standard_aws_credentials_detected=standard_aws_credentials_detected(),
    )


app.mount("/output", StaticFiles(directory=OUTPUT_ROOT), name="output")
