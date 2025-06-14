# ElaraLM

This project provides a simple FastAPI interface for interacting with a language model using Hugging Face transformers. The application is containerized with Docker for easy deployment.

## Quick Start

1. **Build and run with Docker Compose**

   ```bash
   docker-compose up --build
   ```
   
2. Open your browser at `http://localhost:8000` to see the welcome message.

3. Send a POST request to `http://localhost:8000/generate` with JSON body `{ "text": "Your prompt" }` to generate text.

The UI now includes a microphone button for streaming audio directly to the server. Clicking the button will request microphone permissions and visualize the incoming audio while transcribed text is displayed live in the chat.
Transcriptions are labeled with "You said:" and words with low confidence scores are highlighted. Hover over a segment to see the recognition confidence and timestamp or replay the audio.

## Development

Install dependencies locally:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run the application:

```bash
uvicorn app.main:app --reload
```

For a detailed list of features and UI layout, see [docs/system_requirements.md](docs/system_requirements.md).
