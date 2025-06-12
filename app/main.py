from fastapi import FastAPI
from pydantic import BaseModel
from transformers import pipeline
from transformers.pipelines import Pipeline

app = FastAPI(title="ElaraLM")

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

@app.get("/")
def read_root():
    return {"message": "Welcome to ElaraLM"}
