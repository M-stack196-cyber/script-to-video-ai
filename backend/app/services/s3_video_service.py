"""S3 object discovery and atomic download helpers for generated video clips."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def parse_s3_uri(uri: str) -> tuple[str, str]:
    if not isinstance(uri, str) or not uri.strip():
        raise ValueError("S3 URI cannot be empty")
    parsed = urlparse(uri.strip())
    if parsed.scheme.lower() != "s3" or not parsed.netloc:
        raise ValueError("S3 URI must use the format s3://bucket/key-or-prefix")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError("S3 URI cannot contain parameters, a query, or a fragment")
    bucket = parsed.netloc.strip()
    if not bucket or any(character.isspace() for character in bucket):
        raise ValueError("S3 URI bucket is invalid")
    return bucket, parsed.path.lstrip("/")


def _s3_error(operation: str, exc: Exception) -> RuntimeError:
    if isinstance(exc, ClientError):
        error = exc.response.get("Error", {})
        code = str(error.get("Code", "Unknown"))
        return RuntimeError(f"S3 {operation} failed with AWS error code {code}")
    return RuntimeError(f"S3 {operation} failed due to an AWS SDK error")


def list_s3_objects(bucket: str, prefix: str) -> list[dict]:
    if not isinstance(bucket, str) or not bucket.strip():
        raise ValueError("S3 bucket cannot be empty")
    if not isinstance(prefix, str):
        raise ValueError("S3 prefix must be a string")
    objects: list[dict] = []
    try:
        client = boto3.client("s3")
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            contents = page.get("Contents", [])
            if isinstance(contents, list):
                objects.extend(item for item in contents if isinstance(item, dict))
    except (ClientError, BotoCoreError) as exc:
        raise _s3_error("object listing", exc) from exc
    return objects


def find_generated_video_object(s3_uri: str) -> str:
    bucket, prefix = parse_s3_uri(s3_uri)
    objects = list_s3_objects(bucket, prefix)
    extension_priority = {".mp4": 0, ".m4v": 1, ".mov": 2, ".webm": 3}
    candidates: list[tuple[int, str]] = []
    for item in objects:
        key = item.get("Key")
        size = item.get("Size", 0)
        if not isinstance(key, str) or not key or key.endswith("/"):
            continue
        try:
            positive_size = int(size) > 0
        except (TypeError, ValueError):
            positive_size = False
        suffix = Path(key).suffix.lower()
        if positive_size and suffix in extension_priority:
            candidates.append((extension_priority[suffix], key))
    if not candidates:
        raise RuntimeError(f"No non-empty generated video object found beneath {s3_uri}")

    # Prefer MP4 over other recognized video containers, then choose the
    # lexicographically first key so repeated discovery is deterministic.
    _, selected_key = min(
        candidates, key=lambda candidate: (candidate[0], candidate[1])
    )
    return f"s3://{bucket}/{selected_key}"


def download_s3_video(s3_uri: str, destination: Path) -> Path:
    bucket, key = parse_s3_uri(s3_uri)
    if not key:
        raise ValueError("S3 video URI must identify an object key")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.parent / f".{destination.name}.{uuid4().hex}.part"
    try:
        client = boto3.client("s3")
        client.download_file(bucket, key, str(partial))
        if not partial.is_file() or partial.stat().st_size <= 0:
            raise RuntimeError("S3 download produced an empty video file")
        partial.replace(destination)
    except (ClientError, BotoCoreError) as exc:
        raise _s3_error("video download", exc) from exc
    except OSError as exc:
        raise RuntimeError(f"Could not save downloaded video: {exc}") from exc
    finally:
        partial.unlink(missing_ok=True)
    if not destination.is_file() or destination.stat().st_size <= 0:
        raise RuntimeError("Downloaded video file is missing or empty")
    return destination
