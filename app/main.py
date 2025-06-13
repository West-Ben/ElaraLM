
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from transformers import pipeline
from transformers.pipelines import Pipeline

app = FastAPI(title="ElaraLM")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


text_generator: Pipeline | None = None


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


@app.websocket("/ws/audio")
async def audio_stream(websocket: WebSocket):
    """Receive audio chunks and return dummy transcription."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            # Placeholder STT processing
            text = f"Received {len(data)} bytes"
            await websocket.send_json({"text": text})
    except WebSocketDisconnect:
        pass
