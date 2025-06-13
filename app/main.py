
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
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

app = FastAPI(title="ElaraLM")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


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


@app.websocket("/ws/audio")
async def audio_stream(websocket: WebSocket):
    """Receive audio chunks and stream transcription results."""
    await websocket.accept()
    buffer = bytearray()
    threshold = 20000  # bytes before transcription
    try:
        while True:
            data = await websocket.receive_bytes()
            buffer.extend(data)
            if len(buffer) >= threshold:
                text, conf = await transcribe_audio(bytes(buffer))
                await websocket.send_json({"text": text, "final": True, "confidence": conf})
                buffer.clear()
    except WebSocketDisconnect:
        pass
