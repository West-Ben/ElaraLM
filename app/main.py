
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
import logging
import csv
import datetime as dt
import os
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from transformers import pipeline
from transformers.pipelines import Pipeline
import whisper
import ffmpeg
from pydub import AudioSegment
import numpy as np
import io
import asyncio
import base64
import time
from . import tts
import ollama

app = FastAPI(title="ElaraLM")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)


LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'interactions.csv')
os.makedirs(LOG_DIR, exist_ok=True)
if not os.path.isfile(LOG_FILE):
    with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow(['timestamp', 'prompt', 'response', 'tts_model'])

OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'llama3')


text_generator: Pipeline | None = None
stt_model: whisper.Whisper | None = None


def get_stt_model() -> whisper.Whisper:
    """Lazy load and return the Whisper model."""
    global stt_model
    if stt_model is None:
        stt_model = whisper.load_model("base")
    return stt_model


async def transcribe_audio(data: bytes) -> tuple[str, float]:
    """Convert webm/ogg bytes to text using Whisper."""
    process = (
        ffmpeg
        .input("pipe:0")
        .output(
            "pipe:1",
            format="wav",
            ac="1",
            ar="16000",
        )
        .run_async(pipe_stdin=True, pipe_stdout=True, pipe_stderr=True)
    )
    wav_bytes, _ = await asyncio.to_thread(process.communicate, input=data)

    audio_seg = AudioSegment.from_file(io.BytesIO(wav_bytes), format="wav")
    samples = np.array(audio_seg.get_array_of_samples()).astype(np.float32)
    samples /= np.iinfo(audio_seg.array_type).max

    model = get_stt_model()
    result = await asyncio.to_thread(model.transcribe, samples, fp16=False)
    text = result.get("text", "").strip()
    confidence = float(np.exp(result.get("avg_logprob", -10)))
    return text, confidence


def get_pipeline() -> Pipeline:
    """Return a text generation pipeline. Lazily loads the model."""
    global text_generator
    if text_generator is None:
        try:
            text_generator = pipeline("text-generation", model="gpt2")
        except Exception:
            # Fallback dummy pipeline if model can't be loaded
            def _dummy(prompt: str, max_length: int = 50):
                return [
                    {
                        "generated_text": f"[Model unavailable] Echo: {prompt[:max_length]}"
                    }
                ]

            text_generator = _dummy
    return text_generator


async def generate_llm(prompt: str) -> str:
    try:
        resp = await asyncio.to_thread(ollama.generate, model=OLLAMA_MODEL, prompt=prompt)
        if isinstance(resp, dict):
            return resp.get('response', '').strip()
        return str(resp)
    except Exception as e:
        logger.error("LLM unreachable: %s", e)
        with open(os.path.join(LOG_DIR, 'llm_errors.log'), 'a', encoding='utf-8') as f:
            f.write(f"{dt.datetime.utcnow().isoformat()} {e}\n")
        # fall back to local pipeline if available
        pipeline_fn = get_pipeline()
        try:
            result = pipeline_fn(prompt, max_length=50)
            return result[0]["generated_text"]
        except Exception:
            return f"[LLM unreachable] {e}"


def log_interaction(prompt: str, response: str) -> None:
    with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow([
            dt.datetime.utcnow().isoformat(),
            prompt,
            response,
            tts.get_selected_model() or ''
        ])

class Prompt(BaseModel):
    text: str

@app.post("/generate")
async def generate_text(prompt: Prompt):
    """Generate text from the provided prompt and log it."""
    result = await generate_llm(prompt.text)
    log_interaction(prompt.text, result)
    return {"result": result}

@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    """Render the settings page."""
    return templates.TemplateResponse("settings.html", {"request": request})


@app.get("/pipeline", response_class=HTMLResponse)
def pipeline_page(request: Request):
    """Render the pipeline visualization page."""
    return templates.TemplateResponse("pipeline.html", {"request": request})


@app.get("/testing", response_class=HTMLResponse)
def testing_page(request: Request):
    """Render the model testing page."""
    return templates.TemplateResponse("testing.html", {"request": request})


@app.websocket("/ws/audio")
async def audio_stream(websocket: WebSocket):
    """Receive audio chunks and stream transcription results."""
    await websocket.accept()
    buffer = bytearray()
    threshold = 20000  # bytes before transcription
    start_ts = time.time()
    try:
        while True:
            data = await websocket.receive_bytes()
            buffer.extend(data)
            if len(buffer) >= threshold:
                audio_bytes = bytes(buffer)
                text, conf = await transcribe_audio(audio_bytes)
                logger.info("Whisper transcription: %s (%.2f)", text, conf)
                await websocket.send_json(
                    {
                        "text": text,
                        "final": True,
                        "confidence": conf,
                        "timestamp": start_ts,
                        "audio": base64.b64encode(audio_bytes).decode("ascii"),
                    }
                )
                buffer.clear()
                start_ts = time.time()
    except WebSocketDisconnect:
        pass


@app.get("/tts/models")
def get_tts_models():
    """Return available TTS model names and current selection."""
    return {"models": tts.list_models(), "selected": tts.get_selected_model()}


@app.post("/tts/select")
def select_tts_model(name: str):
    """Set the active TTS model."""
    tts.select_model(name)
    return {"selected": name}


@app.websocket("/ws/tts")
async def tts_stream(websocket: WebSocket):
    """Stream synthesized audio bytes for text sent by the client."""
    await websocket.accept()
    try:
        while True:
            text = await websocket.receive_text()
            async for chunk in tts.synthesize_stream(text):
                await websocket.send_bytes(chunk)
            await websocket.send_bytes(b"")
    except WebSocketDisconnect:
        pass
