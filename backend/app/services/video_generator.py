import json
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import settings


NOVA_REEL_PROMPT_LIMIT = 512


def start_video_generation(prompt: str, seed: int = 42) -> str:
    """Start one six-second Amazon Nova Reel text-to-video generation."""
    if not settings.s3_bucket_name.strip():
        raise RuntimeError(
            "S3_BUCKET_NAME is required for Amazon Nova Reel video generation"
        )
    if not settings.bedrock_video_model_id.strip():
        raise RuntimeError("BEDROCK_VIDEO_MODEL_ID is not configured")
    if not prompt.strip():
        raise ValueError("prompt cannot be empty")

    nova_reel_prompt = prompt.strip()[:NOVA_REEL_PROMPT_LIMIT]
    model_input = {
        "taskType": "TEXT_VIDEO",
        "textToVideoParams": {"text": nova_reel_prompt},
        "videoGenerationConfig": {
            "durationSeconds": 6,
            "fps": 24,
            "dimension": "1280x720",
            "seed": seed,
        },
    }
    output_uri = f"s3://{settings.s3_bucket_name.strip()}/nova-reel/"

    try:
        client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
        response = client.start_async_invoke(
            modelId=settings.bedrock_video_model_id,
            modelInput=model_input,
            outputDataConfig={"s3OutputDataConfig": {"s3Uri": output_uri}},
        )
    except ClientError as exc:
        error = exc.response.get("Error", {})
        code = error.get("Code", "Unknown")
        message = error.get("Message", str(exc))
        raise RuntimeError(
            f"Nova Reel generation failed ({code}): {message}"
        ) from exc

    invocation_arn = response.get("invocationArn")
    if not invocation_arn:
        raise RuntimeError("Nova Reel did not return an invocationArn")
    return invocation_arn


def get_video_generation_status(invocation_arn: str) -> dict[str, Any]:
    """Perform one status lookup for an asynchronous Nova Reel invocation."""
    if not invocation_arn.strip():
        raise ValueError("invocation_arn cannot be empty")

    try:
        client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
        response = client.get_async_invoke(invocationArn=invocation_arn)
    except ClientError as exc:
        error = exc.response.get("Error", {})
        code = error.get("Code", "Unknown")
        message = error.get("Message", str(exc))
        raise RuntimeError(
            f"Nova Reel status lookup failed ({code}): {message}"
        ) from exc

    # ResponseMetadata is transport detail; the remaining fields contain the
    # invocation status, output destination, timestamps, and any failure message.
    return {key: value for key, value in response.items() if key != "ResponseMetadata"}


def format_status_for_display(status: dict[str, Any]) -> str:
    """Serialize a Bedrock status response, including datetime values."""
    return json.dumps(status, indent=2, default=str)
