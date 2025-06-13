# System Requirements

This document captures the functional requirements and user interface layout for the ElaraLM application.

## Features

1. **Real-time Speech Input Streaming** – Users can stream microphone audio directly to a speech-to-text (STT) model.
2. **Voice-Activated Microphone** – Optional always-on microphone that only streams audio when voice activity is detected.
3. **Real-Time Speech-to-Text Display** – Transcribed user speech is shown live in the UI.
4. **Transcription Feedback** – The UI highlights uncertain or misrecognized words for quick review.
5. **Real-Time Audio Output Streaming** – Text-to-speech (TTS) audio is streamed directly to speakers without temporary files.
6. **Pre-Synthesis Text Display** – The LLM response text is displayed before being synthesized to audio.
7. **Dynamic Model Selection** – Users select STT, TTS, and LLM models from a folder within the application.
8. **Interactive AI Pipeline Visualization** – A dedicated page visualizes how data flows between the microphone, STT, LLM, and TTS components.
9. **Model Interaction and Testing UI** – Separate testing pages allow interaction with each model individually.
10. **Speech-to-Text Model Test Page** – Streams microphone audio to the chosen STT model and displays the transcription result.
11. **Text-to-Speech Model Test Page** – Lets users type text and play the synthesized audio output.
12. **LLM Direct Interaction Page** – Enables direct text prompts to the LLM and displays the response.

## UI Pages

| Page | Associated Features |
| --- | --- |
| Main Conversation Page | 1, 2, 3, 4, 5, 6 |
| Settings Page | 7, part of 2 |
| AI Pipeline Visualization Page | 8 |
| Model Testing Page | 9 |
| ├─ Speech-to-Text Testing | 9, 10 |
| ├─ Text-to-Speech Testing | 9, 11 |
| └─ LLM Testing | 9, 12 |

The goal of these requirements is to provide a clear roadmap for implementing a conversational interface that can be extended or modified as new models become available.
