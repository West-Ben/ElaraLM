
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
import logging
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

app = FastAPI(title="ElaraLM")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)


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

class Prompt(BaseModel):
    text: str

@app.post("/generate")
def generate_text(prompt: Prompt):
    """Generate text from the provided prompt."""
    pipeline_fn = get_pipeline()
    result = pipeline_fn(prompt.text, max_length=50)
    return {"result": result[0]["generated_text"]}

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
