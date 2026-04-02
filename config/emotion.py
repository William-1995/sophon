"""Emotion-awareness sub-agent: enable flag, model override, signal weights."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .common import safe_env_float


@dataclass(frozen=True)
class EmotionConfig:
    """Weights and toggles for post-run emotion scoring (orb UI).

    Attributes:
        enabled (bool): Run segment analysis after each turn. Env:
            ``SOPHON_EMOTION_ENABLED``.
        model (str | None): Override LLM for emotion only. Env: ``SOPHON_EMOTION_MODEL``.
        user_weight (float): Weight on user text signal. Env:
            ``SOPHON_EMOTION_USER_WEIGHT``.
        system_weight (float): Weight on tool/outcome signal. Env:
            ``SOPHON_EMOTION_SYSTEM_WEIGHT``.
    """

    enabled: bool = field(
        default_factory=lambda: os.environ.get("SOPHON_EMOTION_ENABLED", "true").lower()
        in ("1", "true", "yes"),
    )
    model: str | None = field(
        default_factory=lambda: os.environ.get("SOPHON_EMOTION_MODEL") or None,
    )
    user_weight: float = field(
        default_factory=lambda: safe_env_float("SOPHON_EMOTION_USER_WEIGHT", "0.8"),
    )
    system_weight: float = field(
        default_factory=lambda: safe_env_float("SOPHON_EMOTION_SYSTEM_WEIGHT", "0.2"),
    )
