import shutil
import sys
import tempfile
import os
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.providers.narration import (  # noqa: E402
    LocalEspeakNarrationProvider,
    get_narration_provider,
)
from app.providers.nova_sonic import (  # noqa: E402
    NovaSonicNarrationProvider,
    standard_aws_credentials_detected,
)


def test_provider_selector() -> None:
    original_provider = settings.narration_provider
    try:
        settings.narration_provider = "local"
        assert isinstance(get_narration_provider(), LocalEspeakNarrationProvider)

        settings.narration_provider = "unsupported-provider"
        try:
            get_narration_provider()
        except RuntimeError as exc:
            assert "Unsupported narration provider" in str(exc)
        else:
            raise AssertionError("Expected unknown narration provider failure")
    finally:
        settings.narration_provider = original_provider


def test_local_provider_creates_wav() -> None:
    temporary_directory = Path(tempfile.mkdtemp(prefix="local-narration-"))
    try:
        destination = temporary_directory / "narration.wav"
        result = LocalEspeakNarrationProvider().synthesize(
            "This narration is generated entirely offline.", destination
        )
        assert result == destination
        assert destination.is_file()
        assert destination.stat().st_size > 44
        assert destination.read_bytes()[:4] == b"RIFF"
    finally:
        shutil.rmtree(temporary_directory, ignore_errors=True)


def test_local_provider_missing_espeak() -> None:
    with patch("app.providers.narration.shutil.which", return_value=None):
        try:
            LocalEspeakNarrationProvider().synthesize("Narration", Path("unused.wav"))
        except RuntimeError as exc:
            assert "requires espeak-ng" in str(exc)
        else:
            raise AssertionError("Expected missing espeak-ng failure")


def test_nova_provider_missing_sdk_without_aws_call() -> None:
    with patch("app.providers.nova_sonic.nova_sonic_sdk_available", return_value=False):
        try:
            NovaSonicNarrationProvider().synthesize("Narration", Path("unused.wav"))
        except RuntimeError as exc:
            message = str(exc)
            assert message == "Nova Sonic provider requires aws-sdk-bedrock-runtime"
            assert "secret-test-value" not in message
        else:
            raise AssertionError("Expected missing Nova Sonic SDK failure")


def test_nova_provider_missing_standard_credentials() -> None:
    with patch(
        "app.providers.nova_sonic._load_bedrock_runtime_sdk",
        return_value=object(),
    ), patch(
        "app.providers.nova_sonic.standard_aws_credentials_detected",
        return_value=False,
    ):
        try:
            NovaSonicNarrationProvider().synthesize("Narration", Path("unused.wav"))
        except RuntimeError as exc:
            assert str(exc) == (
                "Nova Sonic requires standard AWS credentials/IAM authentication"
            )
        else:
            raise AssertionError("Expected missing standard credentials failure")


def test_bearer_token_is_not_standard_credentials() -> None:
    with patch.dict(
        os.environ,
        {
            "AWS_BEARER_TOKEN_BEDROCK": "secret-test-value",
            "AWS_SHARED_CREDENTIALS_FILE": "/tmp/nonexistent-codex-credentials",
        },
        clear=True,
    ):
        assert standard_aws_credentials_detected() is False


if __name__ == "__main__":
    test_provider_selector()
    test_local_provider_creates_wav()
    test_local_provider_missing_espeak()
    test_nova_provider_missing_sdk_without_aws_call()
    test_nova_provider_missing_standard_credentials()
    test_bearer_token_is_not_standard_credentials()
    print("Narration provider tests: SUCCESS")
