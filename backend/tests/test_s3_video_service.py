import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.s3_video_service import (  # noqa: E402
    download_s3_video,
    find_generated_video_object,
    list_s3_objects,
    parse_s3_uri,
)


def test_parse_s3_uri() -> None:
    assert parse_s3_uri("s3://example-bucket/jobs/output/") == (
        "example-bucket",
        "jobs/output/",
    )
    for invalid in ("", "https://bucket/key", "s3:///key", "s3://bucket/key?token=x"):
        try:
            parse_s3_uri(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected malformed URI to fail: {invalid}")


def test_list_and_find_generated_video() -> None:
    paginator = MagicMock()
    paginator.paginate.return_value = [
        {"Contents": [{"Key": "prefix/", "Size": 0}]},
        {
            "Contents": [
                {"Key": "prefix/metadata.json", "Size": 20},
                {"Key": "prefix/z-output.mp4", "Size": 200},
                {"Key": "prefix/a-output.mp4", "Size": 100},
            ]
        },
    ]
    client = MagicMock()
    client.get_paginator.return_value = paginator
    with patch("app.services.s3_video_service.boto3.client", return_value=client):
        objects = list_s3_objects("bucket", "prefix/")
    assert len(objects) == 4
    paginator.paginate.assert_called_once_with(Bucket="bucket", Prefix="prefix/")

    with patch(
        "app.services.s3_video_service.list_s3_objects", return_value=objects
    ):
        selected = find_generated_video_object("s3://bucket/prefix/")
    assert selected == "s3://bucket/prefix/a-output.mp4"


def test_download_is_atomic_and_non_empty() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="s3-download-"))
    destination = temporary_directory / "scene.mp4"
    client = MagicMock()

    def write_download(_bucket: str, _key: str, filename: str) -> None:
        Path(filename).write_bytes(b"mock-mp4-content")

    client.download_file.side_effect = write_download
    try:
        with patch("app.services.s3_video_service.boto3.client", return_value=client):
            result = download_s3_video("s3://bucket/output/video.mp4", destination)
        assert result == destination
        assert destination.read_bytes() == b"mock-mp4-content"
        assert not list(temporary_directory.glob("*.part"))
    finally:
        shutil.rmtree(temporary_directory, ignore_errors=True)


def test_failed_download_removes_partial_file() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="s3-download-failure-"))
    destination = temporary_directory / "scene.mp4"
    client = MagicMock()

    def fail_download(_bucket: str, _key: str, filename: str) -> None:
        Path(filename).write_bytes(b"partial")
        raise ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Denied"}},
            "GetObject",
        )

    client.download_file.side_effect = fail_download
    try:
        with patch("app.services.s3_video_service.boto3.client", return_value=client):
            try:
                download_s3_video("s3://bucket/output/video.mp4", destination)
            except RuntimeError as exc:
                assert "AccessDenied" in str(exc)
            else:
                raise AssertionError("Expected mocked S3 download failure")
        assert not destination.exists()
        assert not list(temporary_directory.glob("*.part"))
    finally:
        shutil.rmtree(temporary_directory, ignore_errors=True)


if __name__ == "__main__":
    test_parse_s3_uri()
    test_list_and_find_generated_video()
    test_download_is_atomic_and_non_empty()
    test_failed_download_removes_partial_file()
    print("S3 video service tests: SUCCESS")
