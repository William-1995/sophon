"""
Speech-to-text API router. Mount when SOPHON_SPEECH_ENABLED=1.
"""

import logging
from fastapi import APIRouter, File, HTTPException, UploadFile

from config import get_config
from speech.transcribe import transcribe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Speech"])


@router.get("/speech/status")
def speech_status():
    """Return whether speech-to-text is enabled. Frontend uses this to show/hide mic button."""
    return {"enabled": get_config().speech.enabled}


@router.post("/speech-to-text")
async def speech_to_text(audio: UploadFile = File(...)):
    """Transcribe audio file to text. Accepts webm, wav, mp3, flac."""
    if not get_config().speech.enabled:
        raise HTTPException(status_code=503, detail="Speech-to-text is disabled. Set SOPHON_SPEECH_ENABLED=1.")
    try:
        data = await audio.read()
        if not data:
            raise HTTPException(status_code=400, detail="Empty audio file")
        text = transcribe(data)
        return {"text": text}
    except Exception as e:
        logger.exception("Speech-to-text failed")
        raise HTTPException(status_code=500, detail=str(e))
