"""Backward-compatible wrapper — the implementation lives in ``core.transcribe``.

The desktop app keeps its original behavior (English source, no progress
hooks); the web layer calls ``core.transcribe.transcribe`` directly with its
own options.
"""
from core.transcribe import load_model  # noqa: F401
from core.transcribe import transcribe as _transcribe


def transcribe(audio_path, model_size="small"):
    """Original signature: returns the Whisper segments list."""
    return _transcribe(audio_path, model_size=model_size, language="en")["segments"]
