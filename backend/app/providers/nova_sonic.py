"""Nova Sonic provider foundation for bidirectional Bedrock streaming.

The actual event stream is intentionally not guessed here. It must be completed
against the optional aws-sdk-bedrock-runtime package and its current event API.
"""

from __future__ import annotations

import configparser
import importlib
import importlib.util
import os
import wave
from collections.abc import Iterable
from pathlib import Path
from types import ModuleType
from uuid import uuid4


SDK_MODULE = "aws_sdk_bedrock_runtime"


def nova_sonic_sdk_available() -> bool:
    try:
        return importlib.util.find_spec(SDK_MODULE) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _load_bedrock_runtime_sdk() -> ModuleType:
    if not nova_sonic_sdk_available():
        raise RuntimeError("Nova Sonic provider requires aws-sdk-bedrock-runtime")
    try:
        return importlib.import_module(SDK_MODULE)
    except ImportError as exc:
        raise RuntimeError(
            "Nova Sonic provider requires aws-sdk-bedrock-runtime"
        ) from exc


def standard_aws_credentials_detected() -> bool:
    """Detect configured standard credentials without network/metadata requests."""
    if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
        return True
    if os.getenv("AWS_ROLE_ARN") and os.getenv("AWS_WEB_IDENTITY_TOKEN_FILE"):
        return True
    if os.getenv("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI") or os.getenv(
        "AWS_CONTAINER_CREDENTIALS_FULL_URI"
    ):
        return True

    credentials_file = Path(
        os.getenv("AWS_SHARED_CREDENTIALS_FILE", "~/.aws/credentials")
    ).expanduser()
    profile = os.getenv("AWS_PROFILE", "default")
    parser = configparser.RawConfigParser()
    try:
        if not credentials_file.is_file():
            return False
        parser.read(credentials_file, encoding="utf-8")
        return parser.has_option(profile, "aws_access_key_id") and parser.has_option(
            profile, "aws_secret_access_key"
        )
    except (OSError, configparser.Error):
        return False


def _collect_pcm_chunks(chunks: Iterable[bytes]) -> bytes:
    collected = bytearray()
    for chunk in chunks:
        if not isinstance(chunk, bytes):
            raise RuntimeError("Nova Sonic returned an invalid PCM audio chunk")
        collected.extend(chunk)
    if not collected:
        raise RuntimeError("Nova Sonic returned no PCM audio")
    return bytes(collected)


def _write_pcm_wav(
    pcm_audio: bytes,
    destination: Path,
    *,
    sample_rate: int = 24000,
    channels: int = 1,
    sample_width: int = 2,
) -> Path:
    if not pcm_audio:
        raise RuntimeError("Cannot write an empty Nova Sonic PCM response")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.parent / f".{destination.name}.{uuid4().hex}.part.wav"
    try:
        with wave.open(str(partial), "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_audio)
        if not partial.is_file() or partial.stat().st_size <= 0:
            raise RuntimeError("Nova Sonic produced an empty WAV")
        partial.replace(destination)
    except OSError as exc:
        raise RuntimeError(f"Could not save Nova Sonic narration WAV: {exc}") from exc
    finally:
        partial.unlink(missing_ok=True)
    return destination


class NovaSonicNarrationProvider:
    name = "nova-sonic"

    def _stream_pcm(
        self,
        _sdk: ModuleType,
        _model_id: str,
        _text: str,
        _duration: float | None,
    ) -> Iterable[bytes]:
        raise RuntimeError(
            "Nova Sonic bidirectional streaming is not enabled in this build"
        )

    def synthesize(
        self,
        text: str,
        destination: Path,
        *,
        duration: float | None = None,
    ) -> Path:
        narration = text.strip()
        if not narration:
            raise ValueError("Narration cannot be empty")
        sdk = _load_bedrock_runtime_sdk()
        if not standard_aws_credentials_detected():
            raise RuntimeError(
                "Nova Sonic requires standard AWS credentials/IAM authentication"
            )
        from app.config import settings

        model_id = settings.bedrock_audio_model_id.strip()
        if not model_id:
            raise RuntimeError("BEDROCK_AUDIO_MODEL_ID is not configured")
        pcm_audio = _collect_pcm_chunks(
            self._stream_pcm(sdk, model_id, narration, duration)
        )
        return _write_pcm_wav(pcm_audio, Path(destination))
