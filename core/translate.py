"""Translation to Arabic with pluggable engines.

Engines:

* ``google`` — Google Translate via ``deep-translator`` (default, online),
* ``none``   — passthrough (video is already Arabic / user wants no translation).

Fixes over the original ``app/translator.py``:

* ``translate_batch`` is strictly 1:1 with its input (empty texts are passed
  through untouched instead of being dropped — the old code could silently
  mis-align subtitles),
* progress callback + cancellation between batches,
* configurable source language,
* **rate-limit friendly**: one HTTP request per batch (segments are joined
  with newlines, translated together, then split back), a global throttle
  (Google allows ~5 req/s) and exponential-backoff retries for transient
  errors — the old code fired one request per segment and got 429-bombed,
* resume support: ``known`` prefills already-translated segments and
  ``on_batch`` reports each freshly translated batch so callers can persist
  progress incrementally.
"""
from __future__ import annotations

import random
import re
import threading
import time
from typing import Callable, Dict, List, Mapping, Optional, Sequence

from core.models import PipelineCancelled

DEFAULT_ENGINE = "google"
TARGET_LANGUAGE = "ar"

#: Keep each Google request comfortably below the API's ~5k char limit.
MAX_CHARS_PER_BATCH = 4000
MAX_ITEMS_PER_BATCH = 40

#: Google allows ~5 requests/second — stay comfortably below it.
MIN_REQUEST_INTERVAL = 0.30
REQUEST_JITTER = 0.15

#: Transient failures (rate limits, network, 5xx) are retried with
#: exponential backoff: 2s, 4s, 8s, 16s (30s total budget per request).
RETRY_ATTEMPTS = 5
BACKOFF_BASE_SECONDS = 2.0

#: Errors worth retrying (matched against the exception text).
_TRANSIENT_MARKERS = (
    "too many requests", "429", "rate limit", "rate-limit", "quota",
    "timeout", "timed out", "connection", "temporarily", "unavailable",
    "server error", "bad gateway", "service unavailable",
    " 500", " 502", " 503", "reset by peer", "broken pipe", "unreachable",
    "empty result", "unexpected result", "max retries", "proxy", "ssl",
)

_translator_lock = threading.Lock()
_translators: Dict[tuple, object] = {}

#: Global (cross-thread) rate limiter: earliest next request time.
_throttle_lock = threading.Lock()
_next_request_at = 0.0


def _get_translator(source: str, target: str = TARGET_LANGUAGE):
    """Cached ``GoogleTranslator`` per (source, target) pair."""
    src = source if source and source != "auto" else "auto"
    key = (src, target)
    with _translator_lock:
        translator = _translators.get(key)
        if translator is None:
            from deep_translator import GoogleTranslator

            try:
                translator = GoogleTranslator(source=src, target=target)
            except Exception:
                # Unknown/unsupported source code → let Google detect it.
                translator = GoogleTranslator(source="auto", target=target)
            _translators[key] = translator
        return translator


def _sleep(seconds: float, cancel_event=None) -> None:
    """Interruptible sleep — honours the job's cancel event."""
    deadline = time.monotonic() + max(0.0, seconds)
    while True:
        if cancel_event is not None and cancel_event.is_set():
            raise PipelineCancelled()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(0.15, remaining))


def _throttle(cancel_event=None) -> None:
    """Reserve the next request slot (``MIN_REQUEST_INTERVAL`` + jitter)."""
    global _next_request_at
    with _throttle_lock:
        now = time.monotonic()
        slot = max(now, _next_request_at)
        _next_request_at = slot + MIN_REQUEST_INTERVAL + random.uniform(0.0, REQUEST_JITTER)
        wait = slot - now
    if wait > 0:
        _sleep(wait, cancel_event)


def _backoff_delay(attempt: int) -> float:
    return BACKOFF_BASE_SECONDS * (2 ** attempt) + random.uniform(0.0, 0.5)


def _is_transient(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in text for marker in _TRANSIENT_MARKERS)


def _request(call, cancel_event=None) -> str:
    """Throttle + retry wrapper around a single Google request."""
    last: Optional[BaseException] = None
    for attempt in range(RETRY_ATTEMPTS):
        _throttle(cancel_event)
        try:
            out = call()
        except PipelineCancelled:
            raise
        except Exception as exc:  # noqa: BLE001 — classified below
            last = exc
            if not _is_transient(exc):
                break
        else:
            if isinstance(out, str) and out.strip():
                return out.strip()
            last = RuntimeError("Translation service returned an empty result")
        if attempt + 1 < RETRY_ATTEMPTS:
            _sleep(_backoff_delay(attempt), cancel_event)
    raise RuntimeError(f"Translation failed: {last}") from last


def _pack_indices(indices: Sequence[int], texts: Sequence[str]) -> List[List[int]]:
    """Group indices into batches limited by item count and total chars."""
    batches: List[List[int]] = []
    current: List[int] = []
    chars = 0
    for i in indices:
        cost = len(texts[i]) + 1
        if current and (
            len(current) >= MAX_ITEMS_PER_BATCH or chars + cost > MAX_CHARS_PER_BATCH
        ):
            batches.append(current)
            current, chars = [], 0
        current.append(i)
        chars += cost
    if current:
        batches.append(current)
    return batches


def _translate_one(translator, text: str, cancel_event=None) -> str:
    return _request(lambda: translator.translate(text), cancel_event)


def _translate_chunk(
    translator, chunk: List[str], cancel_event=None
) -> List[str]:
    """Translate one batch with a *single* HTTP request when possible.

    Segments are joined with newlines, sent as one request (instead of one
    request per segment — which is what got us 429-blocked), then split
    back. If Google altered the line structure, or any segment itself
    contains a newline (ambiguous to split), we fall back to per-segment
    requests for that batch only — correctness always wins.
    """
    if len(chunk) == 1 or any("\n" in t or "\r" in t for t in chunk):
        return [_translate_one(translator, text, cancel_event) for text in chunk]

    payload = "\n".join(chunk)
    joined = _request(lambda: translator.translate(payload), cancel_event)
    lines = joined.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if len(lines) == len(chunk) and all(line.strip() for line in lines):
        return [line.strip() for line in lines]
    # Line structure changed → do it the slow, exact way.
    return [_translate_one(translator, text, cancel_event) for text in chunk]


def translate_batch(
    texts: Sequence[str],
    source: str = "en",
    target: str = TARGET_LANGUAGE,
    engine: str = DEFAULT_ENGINE,
    on_progress: Optional[Callable[[float], None]] = None,
    cancel_event=None,
    known: Optional[Mapping[str, str]] = None,
    on_batch: Optional[Callable[[Sequence[str], Sequence[str]], None]] = None,
) -> List[str]:
    """Translate a list of strings, returning a list of the same length.

    Empty/whitespace inputs are passed through unchanged so callers can
    ``zip`` the result with the original segments safely.

    ``known`` maps already-translated source texts to their translations
    (used to resume an interrupted job); ``on_batch`` is invoked with every
    freshly translated batch so callers can persist progress incrementally.
    """
    texts = list(texts)
    if on_progress is None:
        on_progress = lambda _f: None  # noqa: E731

    if not texts:
        on_progress(1.0)
        return []

    # Passthrough engines / already-Arabic source.
    if engine in ("none", "skip", "off") or (source or "").lower() == target:
        on_progress(1.0)
        return list(texts)

    # Separate empty inputs (pass through) from real work.
    pending: List[int] = []
    for i, text in enumerate(texts):
        if text.strip():
            pending.append(i)

    if not pending:
        on_progress(1.0)
        return [t.strip() if t.strip() else t for t in texts]

    known_map: Dict[str, str] = {}
    for key, value in (known or {}).items():
        if key and value:
            known_map[str(key).strip()] = str(value)

    results = list(texts)
    fresh: List[int] = []
    done = 0
    for i in pending:
        hit = known_map.get(texts[i].strip())
        if hit is None:
            fresh.append(i)
        else:
            results[i] = hit
            done += 1
    if done:
        on_progress(done / len(pending))

    if not fresh:
        on_progress(1.0)
        return results

    translator = _get_translator(source, target)
    total = len(pending)

    for batch in _pack_indices(fresh, texts):
        if cancel_event is not None and cancel_event.is_set():
            raise PipelineCancelled()
        chunk = [texts[i].strip() for i in batch]
        translated = _translate_chunk(translator, chunk, cancel_event)
        for i, value in zip(batch, translated):
            results[i] = value
        if on_batch is not None:
            try:
                on_batch(chunk, translated)
            except PipelineCancelled:
                raise
            except Exception:  # noqa: BLE001 — a broken persistence hook must not kill the job
                pass
        done += len(batch)
        on_progress(done / total)

    on_progress(1.0)
    return results
