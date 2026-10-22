"""Backward-compatible wrapper — the implementation lives in ``core.translate``."""
from core.translate import translate_batch as _translate_batch


def translate_batch(texts):
    """Original signature: English → Arabic via Google Translate."""
    return _translate_batch(texts, source="en", target="ar", engine="google")
