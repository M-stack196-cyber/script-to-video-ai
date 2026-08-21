"""Narration provider selection and the local espeak-ng implementation."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Protocol
from uuid import uuid4


class NarrationProvider(Protocol):
    def synthesize(
        self,
        text: str,
        destination: Path,
        *,
        duration: float | None = None,
    ) -> Path: ...


class LocalEspeakNarrationProvider:
    """Offline narration fallback backed by the installed espeak-ng binary."""

    name = "local"

    def synthesize(
        self,
        text: str,
        destination: Path,
        *,
        duration: float | None = None,
    ) -> Path:
        del duration  # Duration enforcement happens during the FFmpeg mux step.
        narration = text.strip()
        if not narration:
            raise ValueError("Narration cannot be empty")
        executable = shutil.which("espeak-ng")
        if executable is None:
            raise RuntimeError("Local narration provider requires espeak-ng")

        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.parent / (
            f".{destination.name}.{uuid4().hex}.part.wav"
        )
        try:
            command = [
                executable,
                "-w",
                str(partial),
                "-s",
                "155",
                "-a",
                "175",
                "--",
                narration,
            ]
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                )
            except OSError as exc:
                raise RuntimeError(f"Could not start espeak-ng: {exc}") from exc
            if completed.returncode != 0:
                detail = completed.stderr.strip() or "unknown error"
                raise RuntimeError(f"espeak-ng narration failed: {detail}")
            if not partial.is_file() or partial.stat().st_size <= 0:
                raise RuntimeError("espeak-ng produced an empty narration WAV")
            partial.replace(destination)
        except OSError as exc:
            raise RuntimeError(f"Could not save local narration WAV: {exc}") from exc
        finally:
            partial.unlink(missing_ok=True)
        return destination


def get_narration_provider() -> NarrationProvider:
    from app.config import settings

    provider_name = settings.narration_provider.strip().lower()
    if provider_name == "local":
        return LocalEspeakNarrationProvider()
    if provider_name == "nova-sonic":
        from app.providers.nova_sonic import NovaSonicNarrationProvider

        return NovaSonicNarrationProvider()
    raise RuntimeError(
        f"Unsupported narration provider: {settings.narration_provider!r}; "
        "expected 'local' or 'nova-sonic'"
    )
