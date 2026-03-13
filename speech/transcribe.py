"""
faster-whisper transcription wrapper.

Lazy-loads model on first request.
"""

import io

from config import get_config

_model = None


def _get_model():
    global _model
    if _model is None:
        cfg = get_config().speech
        from faster_whisper import WhisperModel

        _model = WhisperModel(
            cfg.model,
            device=cfg.device,
            compute_type=cfg.compute_type,
        )
    return _model


def transcribe(audio_bytes: bytes, language: str | None = None) -> str:
    """Transcribe audio bytes to text. Supports wav, webm, mp3, flac (via faster-whisper)."""
    model = _get_model()
    lang = language or get_config().speech.language
    # faster-whisper expects file-like object with read(), not raw bytes
    audio_io = io.BytesIO(audio_bytes)
    segments, _ = model.transcribe(audio_io, language=lang or None)
    return " ".join(s.text.strip() for s in segments).strip()

