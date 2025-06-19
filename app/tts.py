import os
import json
import asyncio
import io
import wave
from typing import List, AsyncIterator

import numpy as np
from TTS.api import TTS as CoquiTTS
from TTS.utils.manage import ModelManager

MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models', 'tts')
_current_model: str | None = None
_engine: CoquiTTS | None = None
_manager: ModelManager | None = None


def _get_manager(output_prefix: str | None = None) -> ModelManager:
    global _manager
    if output_prefix or _manager is None:
        _manager = ModelManager(output_prefix=output_prefix, progress_bar=False)
    return _manager


def _load_config(name: str) -> dict:
    path = os.path.join(MODELS_DIR, name, 'config.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def list_models() -> List[str]:
    if not os.path.isdir(MODELS_DIR):
        return []
    return [n for n in os.listdir(MODELS_DIR)
            if os.path.isfile(os.path.join(MODELS_DIR, n, 'config.json'))]


def list_remote_models() -> List[str]:
    try:
        mgr = _get_manager()
        if hasattr(mgr, 'list_tts_models'):
            return mgr.list_tts_models()
        return mgr.list_models()
    except Exception:
        return []


def _init_engine(name: str) -> CoquiTTS:
    cfg = _load_config(name)
    if cfg.get('type') != 'coqui':
        raise ValueError('Unsupported TTS config')
    args = {}
    if 'model_path' in cfg and 'config_path' in cfg:
        args['model_path'] = os.path.join(MODELS_DIR, name, cfg['model_path'])
        args['config_path'] = os.path.join(MODELS_DIR, name, cfg['config_path'])
        if 'vocoder_path' in cfg and 'vocoder_config_path' in cfg:
            args['vocoder_path'] = os.path.join(MODELS_DIR, name, cfg['vocoder_path'])
            args['vocoder_config_path'] = os.path.join(MODELS_DIR, name, cfg['vocoder_config_path'])
    else:
        args['model_name'] = cfg.get('model_name')
        if 'vocoder_name' in cfg:
            args['vocoder_name'] = cfg['vocoder_name']
    return CoquiTTS(progress_bar=False, **args)


def download_model(remote_name: str, local_name: str | None = None) -> str:
    """Download a model from Coqui and store under models/tts."""
    if local_name is None:
        local_name = remote_name.split('/')[-1].replace('-', '_')
    dest = os.path.join(MODELS_DIR, local_name)
    if os.path.isfile(os.path.join(dest, 'config.json')):
        return local_name
    os.makedirs(dest, exist_ok=True)
    mgr = _get_manager(output_prefix=dest)
    model_path, config_path, info = mgr.download_model(remote_name)
    cfg = {
        'type': 'coqui',
        'model_path': os.path.relpath(model_path, dest),
        'config_path': os.path.relpath(config_path, dest),
    }
    if info.get('default_vocoder'):
        vp, vc, _ = mgr.download_model(info['default_vocoder'])
        cfg['vocoder_path'] = os.path.relpath(vp, dest)
        cfg['vocoder_config_path'] = os.path.relpath(vc, dest)
    with open(os.path.join(dest, 'config.json'), 'w', encoding='utf-8') as f:
        json.dump(cfg, f)
    return local_name


def select_model(name: str) -> None:
    global _current_model, _engine
    if name not in list_models():
        raise ValueError(f"Model '{name}' not found")
    _engine = _init_engine(name)
    _current_model = name


def get_selected_model() -> str | None:
    return _current_model


def _array_to_wav_bytes(arr: np.ndarray, sample_rate: int) -> bytes:
    arr = np.clip(arr, -1.0, 1.0)
    arr_i16 = (arr * 32767).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(arr_i16.tobytes())
    return buffer.getvalue()


async def synthesize_stream(text: str) -> AsyncIterator[bytes]:
    global _engine
    if _engine is None:
        models = list_models()
        if not models:
            raise RuntimeError('No TTS models available')
        select_model(models[0])
    # --- Begin change: handle multi-speaker models ---
    tts_kwargs = {}
    if hasattr(_engine, "speakers") and _engine.speakers:
        tts_kwargs["speaker"] = _engine.speakers[0]
    audio = await asyncio.to_thread(_engine.tts, text, **tts_kwargs)
    # --- End change ---
    sr = getattr(_engine.synthesizer, 'output_sample_rate', 22050)
    wav_bytes = _array_to_wav_bytes(audio, sr)
    for i in range(0, len(wav_bytes), 2048):
        yield wav_bytes[i:i+2048]
