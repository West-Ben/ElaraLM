import os
import json
from typing import List, Tuple

import whisper
import logging

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "stt")
_current_model: str | None = None
_engine: whisper.Whisper | None = None

logger = logging.getLogger(__name__)


def _load_config(name: str) -> dict:
    path = os.path.join(MODELS_DIR, name, "config.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def list_models() -> List[str]:
    if not os.path.isdir(MODELS_DIR):
        return []
    return [
        n
        for n in os.listdir(MODELS_DIR)
        if os.path.isfile(os.path.join(MODELS_DIR, n, "config.json"))
    ]


def select_model(name: str) -> None:
    global _engine, _current_model
    if name not in list_models():
        raise ValueError(f"Model '{name}' not found")
    cfg = _load_config(name)
    model_name = cfg.get("model_name", name)
    _engine = whisper.load_model(model_name)
    _current_model = name
    logger.info("Selected STT model: %s", name)


def get_selected_model() -> str | None:
    return _current_model


def transcribe_audio(samples) -> Tuple[str, float]:
    global _engine
    if _engine is None:
        models = list_models()
        if models:
            select_model(models[0])
        else:
            _engine = whisper.load_model("base")
            _current_model = "base"
    logger.debug("Transcribing %d samples", len(samples))
    result = _engine.transcribe(samples, fp16=False)
    text = result.get("text", "").strip()
    confidence = float(result.get("avg_logprob", -10))
    logger.debug("STT result: '%s' (%.2f)", text, confidence)
    return text, confidence
