# ElaraLM

This project provides a simple FastAPI interface for interacting with a language model using Hugging Face transformers. The application is containerized with Docker for easy deployment.

## Quick Start

1. **Build and run with Docker Compose**

   ```bash
   docker-compose up --build
   ```

2. Open your browser at `http://localhost:8000` to see the welcome message.

3. Send a POST request to `http://localhost:8000/generate` with JSON body `{ "text": "Your prompt" }` to generate text.

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
