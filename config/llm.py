"""Default chat model identifier (provider resolution lives in ``providers``)."""

from __future__ import annotations

from dataclasses import dataclass

from .defaults import DEFAULT_MODEL


@dataclass(frozen=True)
class LLMConfig:
    """Single-field default for model selection when the request omits ``model``.

    Attributes:
        default_model (str): Default model id used when requests omit ``model``.
    """

    default_model: str = DEFAULT_MODEL
