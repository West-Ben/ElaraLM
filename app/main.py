from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
import logging
import csv
import datetime as dt
import os
from fastapi.responses import HTMLResponse, JSONResponse

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from transformers import pipeline
from transformers.pipelines import Pipeline
import ffmpeg
from pydub import AudioSegment
import numpy as np
import io
import asyncio
import base64
import time
from . import tts, stt, llm
import httpx


app = FastAPI(title="ElaraLM")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Configure application logging
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
APP_LOG = os.path.join(LOG_DIR, "app.log")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(APP_LOG),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


LOG_FILE = os.path.join(LOG_DIR, "interactions.csv")
if not os.path.isfile(LOG_FILE):
    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["timestamp", "prompt", "response", "tts_model"])


text_generator: Pipeline | None = None


async def transcribe_audio(data: bytes) -> tuple[str, float]:
    """Convert webm/ogg bytes to text using Whisper."""
    logger.debug("Transcribing %d bytes of audio", len(data))
    process = (
        ffmpeg.input("pipe:0")
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

    text, logprob = await asyncio.to_thread(stt.transcribe_audio, samples)
    confidence = float(np.exp(logprob))
    logger.debug("Transcription result: '%s' (%.2f)", text, confidence)
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
    """Generate text using the selected LLM, falling back to local pipeline."""
    result = await llm.generate(prompt)
    if result:
        return result
    pipeline_fn = get_pipeline()
    try:
        result = pipeline_fn(prompt, max_length=50)
        return result[0]["generated_text"]
    except Exception as e:
        return f"[LLM unreachable] {e}"


def log_interaction(prompt: str, response: str) -> None:
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(
            [
                dt.datetime.utcnow().isoformat(),
                prompt,
                response,
                tts.get_selected_model() or "",
            ]
        )


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
    logger.info("/ws/audio connected")
    buffer = bytearray()
    threshold = 20000  # bytes before transcription
    start_ts = time.time()
    try:
        while True:
            data = await websocket.receive_bytes()
            logger.debug("Received audio chunk %d bytes", len(data))
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
        logger.info("/ws/audio disconnected")


@app.get("/tts/models")
def get_tts_models():
    """Return available TTS model names and current selection."""
    return {"models": tts.list_models(), "selected": tts.get_selected_model()}


@app.post("/tts/select")
def select_tts_model(name: str):
    """Set the active TTS model."""
    tts.select_model(name)
    return {"selected": name}


@app.get("/tts/available")
def available_tts_models():
    """Return remote Coqui TTS model names."""
    return {"models": tts.list_remote_models()}


class DownloadRequest(BaseModel):
    name: str


@app.post("/tts/download")
def download_tts_model(req: DownloadRequest):
    try:
        local = tts.download_model(req.name)
        return {"model": local}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.websocket("/ws/tts")
async def tts_stream(websocket: WebSocket):
    """Stream synthesized audio bytes for text sent by the client."""
    await websocket.accept()
    logger.info("/ws/tts connected")
    try:
        while True:
            text = await websocket.receive_text()
            logger.info("TTS request: %s", text)
            async for chunk in tts.synthesize_stream(text):
                logger.debug("Sending TTS chunk %d bytes", len(chunk))
                await websocket.send_bytes(chunk)
            await websocket.send_bytes(b"")
    except WebSocketDisconnect:
        logger.info("/ws/tts disconnected")




class LLMSelect(BaseModel):
    source: str
    name: str
    url: str | None = None
    key: str | None = None


@app.get("/llm/models")
async def get_llm_models(source: str = "local"):
    if source == "remote":
        models = await llm.list_remote_models()
    else:
        models = await llm.list_local_models()
    return {"models": models}


@app.post("/llm/select")
def select_llm_model(req: LLMSelect):
    llm.select_model(req.source, req.name, req.url, req.key)
    return {"selected": req.name, "source": req.source}
