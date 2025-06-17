import os
import subprocess
from typing import List

import httpx

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434')
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.json')

_current_source = 'local'
_current_model: str | None = None
_llmstudio_url: str | None = os.environ.get('LLMSTUDIO_URL')
_llmstudio_key: str | None = os.environ.get('LLMSTUDIO_KEY')


def _save_config() -> None:
    try:
        data = {
            'source': _current_source,
            'model': _current_model,
            'llmstudio_url': _llmstudio_url,
            'llmstudio_key': _llmstudio_key,
        }
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            import json
            json.dump({'llm': data}, f)
    except Exception:
        pass


def _load_config() -> None:
    global _current_source, _current_model, _llmstudio_url, _llmstudio_key
    try:
        import json
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f).get('llm', {})
            _current_source = cfg.get('source', 'local')
            _current_model = cfg.get('model')
            _llmstudio_url = cfg.get('llmstudio_url')
            _llmstudio_key = cfg.get('llmstudio_key')
    except Exception:
        pass


_load_config()


async def list_local_models() -> List[str]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f'{OLLAMA_URL}/api/tags')
            resp.raise_for_status()
            return [m['name'] for m in resp.json().get('models', [])]
    except Exception:
        try:
            out = subprocess.check_output(['ollama', 'list'], text=True)
            return [line.split(':')[0] for line in out.splitlines() if line]
        except Exception:
            return []


async def list_remote_models() -> List[str]:
    if not _llmstudio_url:
        return []
    try:
        headers = {'Authorization': f'Bearer {_llmstudio_key}'} if _llmstudio_key else {}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_llmstudio_url.rstrip('/') + '/models', headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data.get('models', [])
    except Exception:
        return []


def select_model(source: str, name: str, url: str | None = None, key: str | None = None) -> None:
    global _current_source, _current_model, _llmstudio_url, _llmstudio_key
    _current_source = source
    _current_model = name
    if url:
        _llmstudio_url = url
    if key:
        _llmstudio_key = key
    _save_config()


async def generate(prompt: str) -> str:
    if _current_source == 'remote' and _llmstudio_url:
        headers = {'Authorization': f'Bearer {_llmstudio_key}'} if _llmstudio_key else {}
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    _llmstudio_url.rstrip('/') + '/v1/chat/completions',
                    headers=headers,
                    json={'model': _current_model, 'messages': [{'role': 'user', 'content': prompt}]}
                )
                resp.raise_for_status()
                data = resp.json()
                choice = data.get('choices', [{}])[0]
                return choice.get('message', {}).get('content', '').strip()
        except Exception:
            pass
    else:
        url = f'{OLLAMA_URL}/api/generate'
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(url, json={'model': _current_model or 'llama3', 'prompt': prompt})
                resp.raise_for_status()
                data = resp.json()
                return data.get('response', data.get('generated_text', '')).strip()
        except Exception:
            pass
    return ''


