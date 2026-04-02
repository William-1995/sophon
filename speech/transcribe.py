"""
faster-whisper transcription wrapper.

Lazy-loads model on first request.
"""

import io

from config import get_config


class _WhisperModelLoader:
    """Loads and caches WhisperModel once per process (config read at first use)."""

    __slots__ = ("_model",)

    def __init__(self) -> None:
        self._model = None

    def get(self):
        if self._model is None:
            cfg = get_config().speech
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                cfg.model,
                device=cfg.device,
                compute_type=cfg.compute_type,
            )
        return self._model


_loader = _WhisperModelLoader()

def transcribe(audio_bytes: bytes, language: str | None = None) -> str:
    """Transcribe audio bytes to text. Supports wav, webm, mp3, flac (via faster-whisper)."""
    model = _loader.get()
    lang = language or get_config().speech.language
    # faster-whisper expects file-like object with read(), not raw bytes
    audio_io = io.BytesIO(audio_bytes)
    segments, _ = model.transcribe(audio_io, language=lang or None)
    return " ".join(s.text.strip() for s in segments).strip()
