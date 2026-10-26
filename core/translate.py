"""Translation to Arabic with pluggable engines.

Engines:

* ``google`` — Google Translate via ``deep-translator`` (default, online),
* ``argos``  — **offline** translation via Argos Translate (no internet),
* ``none``   — passthrough (video is already Arabic / user wants no translation).

When Google is rate-limited (429) and its backoff budget is exhausted, the
``google`` engine **automatically falls back to the offline translator** for
a cooldown window (``GOOGLE_FALLBACK_COOLDOWN``) instead of failing the job —
and goes back to Google by itself once the window passes.

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

#: Backoff schedules (seconds to wait before each retry). A Google 429 is a
#: *cooldown* that lasts minutes, so rate-limit errors get a much longer
#: budget than ordinary network blips.
TRANSIENT_DELAYS = (2, 4, 8, 16)           # 5 attempts, ~30s total
RATE_LIMIT_DELAYS = (5, 15, 30, 60, 120)   # 6 attempts, ~4min total

#: Offline fallback engine (Argos Translate). Used when the user picks
#: ``engine="argos"``, and automatically while Google is unreachable.
OFFLINE_ENGINE = "argos"

#: After Google gives up (full backoff exhausted), skip it for this long and
#: translate locally; afterwards Google gets another chance by itself.
GOOGLE_FALLBACK_COOLDOWN = 600.0  # seconds

_google_lock = threading.Lock()
_google_blocked_until = 0.0
_offline_pair_cache: Dict[tuple, object] = {}
_offline_install_lock = threading.Lock()

#: Errors worth retrying (matched against the exception text).
_TRANSIENT_MARKERS = (
    "too many requests", "429", "rate limit", "rate-limit", "quota",
    "timeout", "timed out", "connection", "temporarily", "unavailable",
    "server error", "bad gateway", "service unavailable",
    " 500", " 502", " 503", "reset by peer", "broken pipe", "unreachable",
    "empty result", "unexpected result", "max retries", "proxy", "ssl",
)
_RATE_LIMIT_MARKERS = ("too many requests", "429", "rate limit", "rate-limit", "quota")

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


def _is_transient(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in text for marker in _TRANSIENT_MARKERS)


def _is_rate_limit(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in text for marker in _RATE_LIMIT_MARKERS)


def _request(call, cancel_event=None, on_note=None) -> str:
    """Throttle + retry wrapper around a single Google request.

    Rate-limit errors (Google 429 — a cooldown of minutes) retry on the long
    ``RATE_LIMIT_DELAYS`` schedule; other transient errors use the short one.
    ``on_note`` (if given) is called with a human-readable message before
    each wait so the UI can show why the job is pausing.
    """
    last: Optional[BaseException] = None
    attempt = 0
    while True:
        _throttle(cancel_event)
        try:
            out = call()
        except PipelineCancelled:
            raise
        except Exception as exc:  # noqa: BLE001 — classified below
            if not _is_transient(exc):
                last = exc
                break
            last = exc
            delays = RATE_LIMIT_DELAYS if _is_rate_limit(exc) else TRANSIENT_DELAYS
        else:
            if isinstance(out, str) and out.strip():
                return out.strip()
            last = RuntimeError("Translation service returned an empty result")
            delays = TRANSIENT_DELAYS
        if attempt >= len(delays):
            break
        delay = delays[attempt] + random.uniform(0.0, 0.5)
        attempt += 1
        if on_note is not None:
            try:
                why = "Rate-limited by Google" if _is_rate_limit(last) else "Transient error"
                on_note(f"{why} — waiting {delay:.0f}s before retry {attempt}/{len(delays)}…")
            except Exception:  # noqa: BLE001 — a broken note hook must not kill the job
                pass
        _sleep(delay, cancel_event)
    hint = ""
    if _is_rate_limit(last):
        hint = (
            " — Google is rate-limiting this connection. Wait a few minutes, "
            "then press ↻ Retry (your transcript and translations are saved)."
        )
    raise RuntimeError(f"Translation failed: {last}{hint}") from last


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


def _translate_one(translator, text: str, cancel_event=None, on_note=None) -> str:
    return _request(lambda: translator.translate(text), cancel_event, on_note)


def _translate_chunk(
    translator, chunk: List[str], cancel_event=None, on_note=None
) -> List[str]:
    """Translate one batch with a *single* HTTP request when possible.

    Segments are joined with newlines, sent as one request (instead of one
    request per segment — which is what got us 429-blocked), then split
    back. If Google altered the line structure, or any segment itself
    contains a newline (ambiguous to split), we fall back to per-segment
    requests for that batch only — correctness always wins.
    """
    if len(chunk) == 1 or any("\n" in t or "\r" in t for t in chunk):
        return [_translate_one(translator, text, cancel_event, on_note) for text in chunk]

    payload = "\n".join(chunk)
    joined = _request(lambda: translator.translate(payload), cancel_event, on_note)
    lines = joined.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if len(lines) == len(chunk) and all(line.strip() for line in lines):
        return [line.strip() for line in lines]
    # Line structure changed → do it the slow, exact way.
    return [_translate_one(translator, text, cancel_event, on_note) for text in chunk]


# ── Offline engine (Argos Translate) ───────────────────────────────────────
def offline_available() -> bool:
    """True when ``argostranslate`` (the offline engine) is importable."""
    try:
        import argostranslate.translate  # noqa: F401
        return True
    except Exception:  # noqa: BLE001 — absence must never break the app
        return False


def _offline_pair(source: str, target: str):
    """Installed Argos translation object for source→target, or ``None``."""
    src = (source or "en").strip().lower()
    if not src or src == "auto":
        src = "en"  # this project assumes English speech (whisper gives real codes)
    key = (src, target)
    cached = _offline_pair_cache.get(key)
    if cached is not None:
        return cached
    try:
        from argostranslate import translate as argos

        # Official lookup (handles this version's translations_from layout).
        translation = argos.get_translation_from_codes(src, target)
    except Exception:  # noqa: BLE001 — not installed / unknown code
        return None
    if translation is None:
        return None
    try:
        if translation.from_lang.code != src or translation.to_lang.code != target:
            return None  # identity / pivot wrappers are not what we asked for
    except Exception:  # noqa: BLE001
        return None
    _offline_pair_cache[key] = translation
    return translation


def ensure_offline_package(on_note=None) -> None:
    """Download + install the English→Arabic offline package once (~100 MB).

    After the first successful run the package lives on disk and every later
    translation works with **no internet at all**.
    """
    if _offline_pair("en", "ar") is not None:
        return
    with _offline_install_lock:
        if _offline_pair("en", "ar") is not None:
            return
        if not offline_available():
            raise RuntimeError(
                "Offline translator not installed — run: pip install argostranslate"
            )
        try:
            from argostranslate import package as argos_package

            argos_package.update_package_index()
            candidates = [
                p
                for p in argos_package.get_available_packages()
                if getattr(p, "from_code", None) == "en"
                and getattr(p, "to_code", None) == "ar"
            ]
            if not candidates:
                raise RuntimeError("no English→Arabic package in the index")
            _note(on_note, "Downloading the offline translation package (~100 MB) — one time only…")
            argos_package.install_from_path(candidates[0].download())
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Offline translation package unavailable: {exc}. "
                "Check the internet once (it downloads a single time), "
                "or choose Google / English as the translation language."
            ) from exc
        if _offline_pair("en", "ar") is None:
            raise RuntimeError("Offline package installed but not detected — restart the app")


def _offline_translate_batch(
    chunk: Sequence[str],
    source: str,
    target: str,
    cancel_event=None,
    on_note=None,
) -> List[str]:
    """Translate one batch locally with Argos (no network after install)."""
    ensure_offline_package(on_note)
    pair = _offline_pair(source, target)
    if pair is None:
        raise RuntimeError(
            f"Offline translator has no {source or 'auto'}→{target} pair "
            "(English→Arabic is what it ships with)"
        )
    out: List[str] = []
    for text in chunk:
        if cancel_event is not None and cancel_event.is_set():
            raise PipelineCancelled()
        try:
            value = pair.translate(text)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Offline translation failed: {exc}") from exc
        out.append((value or "").strip() or text)
    return out


def _note(on_note, message: str) -> None:
    """Emit a notice without letting a broken hook kill the job."""
    if on_note is None:
        return
    try:
        on_note(message)
    except Exception:  # noqa: BLE001
        pass


def reset_fallback() -> None:
    """Clear the Google-cooldown window (tests / manual recovery)."""
    global _google_blocked_until
    with _google_lock:
        _google_blocked_until = 0.0


def _google_is_blocked() -> bool:
    with _google_lock:
        return time.monotonic() < _google_blocked_until


def _mark_google_blocked() -> None:
    global _google_blocked_until
    with _google_lock:
        _google_blocked_until = time.monotonic() + GOOGLE_FALLBACK_COOLDOWN


def translate_batch(
    texts: Sequence[str],
    source: str = "en",
    target: str = TARGET_LANGUAGE,
    engine: str = DEFAULT_ENGINE,
    on_progress: Optional[Callable[[float], None]] = None,
    cancel_event=None,
    known: Optional[Mapping[str, str]] = None,
    on_batch: Optional[Callable[[Sequence[str], Sequence[str]], None]] = None,
    on_note: Optional[Callable[[str], None]] = None,
) -> List[str]:
    """Translate a list of strings, returning a list of the same length.

    Empty/whitespace inputs are passed through unchanged so callers can
    ``zip`` the result with the original segments safely.

    ``known`` maps already-translated source texts to their translations
    (used to resume an interrupted job); ``on_batch`` is invoked with every
    freshly translated batch so callers can persist progress incrementally;
    ``on_note`` receives human-readable notices (e.g. "waiting Ns before
    retry") so callers can show why the job appears to pause.
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

    # ── Engine routing: offline (argos), Google, or Google→offline fallback ──
    if engine == OFFLINE_ENGINE and not offline_available():
        raise RuntimeError(
            "Offline translator not installed — run: pip install argostranslate "
            "(then it works without internet), or choose Google / English instead."
        )
    use_offline = engine == OFFLINE_ENGINE or (
        engine == "google" and _google_is_blocked() and offline_available()
    )
    translator = None if use_offline else _get_translator(source, target)
    total = len(pending)

    for batch in _pack_indices(fresh, texts):
        if cancel_event is not None and cancel_event.is_set():
            raise PipelineCancelled()
        chunk = [texts[i].strip() for i in batch]
        if use_offline:
            translated = _offline_translate_batch(
                chunk, source, target, cancel_event, on_note
            )
        else:
            try:
                translated = _translate_chunk(translator, chunk, cancel_event, on_note)
            except RuntimeError as google_exc:
                # Google exhausted its backoff → keep the job alive offline.
                if engine != "google" or not offline_available():
                    raise
                _mark_google_blocked()
                use_offline = True
                translator = None
                try:
                    translated = _offline_translate_batch(
                        chunk, source, target, cancel_event, on_note
                    )
                except PipelineCancelled:
                    raise
                except Exception as local_exc:  # noqa: BLE001
                    raise RuntimeError(
                        f"{google_exc}\nOffline fallback unavailable: {local_exc}"
                    ) from google_exc
                _note(
                    on_note,
                    "⚠ Google unavailable — switched to the offline translator "
                    "for this run (no internet needed from here on)",
                )
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
