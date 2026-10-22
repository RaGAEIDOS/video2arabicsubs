"""Speech-to-text via OpenAI Whisper.

Features on top of the original ``app/transcriber.py``:

* ``language`` is configurable (``None`` / ``"auto"`` = auto-detect),
* thread-safe model cache and serialized inference,
* real per-frame progress reporting by hooking Whisper's internal tqdm,
* cooperative cancellation (raises :class:`PipelineCancelled` from inside
  the transcription loop).

``whisper`` is imported lazily so importing this module is cheap.
"""
from __future__ import annotations

import importlib
import os
import shutil
import threading
from typing import Callable, Optional

from core.models import PipelineCancelled

_model = None
_model_name: Optional[str] = None
_model_lock = threading.Lock()      # protects the cached model
_infer_lock = threading.RLock()     # serializes inference + progress hook install


# ── ffmpeg on PATH (Windows convenience, from the original module) ────────
def ensure_ffmpeg_on_path() -> None:
    try:
        import imageio_ffmpeg

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_dir = os.path.dirname(ffmpeg_exe)
        if os.name == "nt":
            ffmpeg_link = os.path.join(ffmpeg_dir, "ffmpeg.exe")
            if not os.path.exists(ffmpeg_link):
                shutil.copy2(ffmpeg_exe, ffmpeg_link)
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass


ensure_ffmpeg_on_path()


def load_model(model_size: str = "small"):
    """Load (and cache) a Whisper model. Thread-safe."""
    global _model, _model_name
    with _model_lock:
        if _model is None or _model_name != model_size:
            whisper = importlib.import_module("whisper")
            _model = whisper.load_model(model_size)
            _model_name = model_size
        return _model


# ── Progress hook ─────────────────────────────────────────────────────────
class _ReportingBar:
    """Drop-in replacement for ``tqdm.tqdm`` inside whisper.transcribe."""

    def __init__(self, total: float = 0, *args, **kwargs):
        self.total = float(total or 0)
        self.n = 0.0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def update(self, n: float = 1) -> None:
        if _progress_hook_cancel_event is not None and _progress_hook_cancel_event.is_set():
            raise PipelineCancelled()
        if _progress_hook_callback is None:
            return
        self.n += n
        if self.total > 0:
            _progress_hook_callback(max(0.0, min(1.0, self.n / self.total)))

    # tqdm API surface that whisper may touch (never actually used by us).
    def close(self):  # pragma: no cover
        pass

    def refresh(self, *args, **kwargs):  # pragma: no cover
        pass

    def set_description(self, *args, **kwargs):  # pragma: no cover
        pass

    def unpause(self):  # pragma: no cover
        pass


_progress_hook_callback: Optional[Callable[[float], None]] = None
_progress_hook_cancel_event = None


class _HookedTqdmNamespace:
    """Object whose ``.tqdm`` attribute is our reporting bar."""

    tqdm = _ReportingBar


def _install_progress_hook(on_progress, cancel_event):
    """Patch ``whisper.transcribe.tqdm`` for the duration of a call.

    Returns a restore callable, or ``None`` when the hook cannot be
    installed (whisper not installed / different internal layout) — in
    which case the pipeline simply reports stage-level progress.
    """
    global _progress_hook_callback, _progress_hook_cancel_event

    if on_progress is None:
        return None
    try:
        module = importlib.import_module("whisper.transcribe")
    except Exception:
        return None
    original = getattr(module, "tqdm", None)
    if original is None or not hasattr(original, "tqdm"):
        return None

    _progress_hook_callback = on_progress
    _progress_hook_cancel_event = cancel_event
    module.tqdm = _HookedTqdmNamespace()

    def restore() -> None:
        global _progress_hook_callback, _progress_hook_cancel_event
        try:
            module.tqdm = original
        except Exception:  # pragma: no cover
            pass
        _progress_hook_callback = None
        _progress_hook_cancel_event = None

    return restore


# ── Transcription ─────────────────────────────────────────────────────────
def transcribe(
    audio_path: str,
    model_size: str = "small",
    language: Optional[str] = "en",
    on_progress: Optional[Callable[[float], None]] = None,
    cancel_event=None,
) -> dict:
    """Transcribe a WAV file.

    Returns ``{"segments": [...], "language": "<iso639-1>"}``.
    ``language`` may be ``None``/``"auto"`` to enable detection.
    """
    whisper = importlib.import_module("whisper")
    lang = None if language in (None, "", "auto") else language

    with _infer_lock:
        model = load_model(model_size)
        restore = _install_progress_hook(on_progress, cancel_event)
        try:
            if cancel_event is not None and cancel_event.is_set():
                raise PipelineCancelled()
            result = whisper.transcribe(model, audio_path, language=lang, verbose=False)
        finally:
            if restore:
                restore()

    segments = [seg for seg in result.get("segments", []) if seg.get("text", "").strip()]
    detected = result.get("language") or lang or "en"
    return {"segments": segments, "language": detected}
