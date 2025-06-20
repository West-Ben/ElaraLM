import logging
from typing import Tuple

import whisper

_engine: whisper.Whisper | None = None
logger = logging.getLogger(__name__)


def transcribe_audio(samples) -> Tuple[str, float]:
    """Transcribe audio samples using the Whisper base model."""
    global _engine
    if _engine is None:
        _engine = whisper.load_model("base")
        logger.info("Loaded Whisper base model for STT")
    logger.debug("Transcribing %d samples", len(samples))
    result = _engine.transcribe(samples, fp16=False)
    text = result.get("text", "").strip()
    confidence = float(result.get("avg_logprob", -10))
    logger.debug("STT result: '%s' (%.2f)", text, confidence)
    return text, confidence
