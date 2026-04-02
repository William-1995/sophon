"""Local speech-to-text (faster-whisper) defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SpeechConfig:
    """STT feature toggle and faster-whisper runtime options.

    Attributes:
        enabled (bool): Master switch for speech routes. Env: ``SOPHON_SPEECH_ENABLED``.
        model (str): Whisper size name (``tiny``, ``base``, …). Env:
            ``SOPHON_SPEECH_MODEL``.
        language (str | None): ISO code or None for auto. Env: ``SOPHON_SPEECH_LANGUAGE``.
        device (str): ``cpu`` or ``cuda``. Env: ``SOPHON_SPEECH_DEVICE``.
        compute_type (str): e.g. ``int8`` on CPU. Env: ``SOPHON_SPEECH_COMPUTE``.
    """

    enabled: bool = field(
        default_factory=lambda: os.environ.get("SOPHON_SPEECH_ENABLED", "1").lower()
        in ("1", "true", "yes"),
    )
    model: str = field(default_factory=lambda: os.environ.get("SOPHON_SPEECH_MODEL", "base"))
    language: str | None = field(
        default_factory=lambda: os.environ.get("SOPHON_SPEECH_LANGUAGE") or None,
    )
    device: str = field(default_factory=lambda: os.environ.get("SOPHON_SPEECH_DEVICE", "cpu"))
    compute_type: str = field(
        default_factory=lambda: os.environ.get("SOPHON_SPEECH_COMPUTE", "int8"),
    )
