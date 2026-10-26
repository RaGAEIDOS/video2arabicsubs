"""The GUI/server-agnostic subtitle pipeline.

    extract audio → transcribe → translate → generate SRT/VTT (→ burn-in)

Every stage reports structured :class:`ProgressEvent` objects through
``on_event`` (overall 0–100 % plus per-stage detail), honours a
``threading.Event`` for cancellation, and wraps failures in
:class:`StageError` so callers know *which* stage failed.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from core import audio as audio_mod
from core import subtitles
from core import transcribe as transcribe_mod
from core import translate as translate_mod
from core.models import (
    Cue,
    JobOptions,
    PipelineCancelled,
    ProgressEvent,
    Stage,
    StageError,
)

#: Minimum interval between non-forced progress events (seconds).
EVENT_THROTTLE = 0.25

#: Stage weights (must sum to 100 for each variant).
_WEIGHTS_WITHOUT_BURN = {
    Stage.EXTRACTING: 15.0,
    Stage.TRANSCRIBING: 55.0,
    Stage.TRANSLATING: 20.0,
    Stage.GENERATING: 10.0,
}
_WEIGHTS_WITH_BURN = {
    Stage.EXTRACTING: 10.0,
    Stage.TRANSCRIBING: 45.0,
    Stage.TRANSLATING: 18.0,
    Stage.GENERATING: 7.0,
    Stage.BURNING: 20.0,
}


@dataclass
class PipelineResult:
    cues: List[Cue]
    language: str
    duration: Optional[float]
    files: Dict[str, str] = field(default_factory=dict)  # "srt"/"vtt"/"video" → path
    warnings: List[str] = field(default_factory=list)


class _Emitter:
    """Turns stage transitions into weighted overall percentages."""

    def __init__(self, on_event, offset: float, scale: float, weights: Dict[Stage, float]):
        self._on_event = on_event
        self._offset = float(offset)
        self._scale = float(scale)
        self._weights = weights
        self._completed_weight = 0.0
        self._stage: Optional[Stage] = None
        self._stage_frac = 0.0
        self._stage_has_detail = False
        self._last_ts = 0.0

    # ── event plumbing ────────────────────────────────────────────────
    def _overall(self) -> float:
        weight = self._weights.get(self._stage, 0.0) if self._stage else 0.0
        frac = self._completed_weight + weight * self._stage_frac
        raw = self._offset + self._scale * (frac / 100.0)
        return max(0.0, min(100.0, raw))

    def _emit(self, message: str = "", force: bool = False) -> None:
        if self._on_event is None:
            return
        now = time.monotonic()
        if not force and (now - self._last_ts) < EVENT_THROTTLE:
            return
        self._last_ts = now
        event = ProgressEvent(
            stage=self._stage or Stage.QUEUED,
            percent=self._overall(),
            stage_percent=self._stage_frac if self._stage_has_detail else None,
            message=message,
        )
        try:
            self._on_event(event)
        except Exception:  # noqa: BLE001 — a broken callback must not kill the job
            pass

    # ── stage transitions ─────────────────────────────────────────────
    def start(self, stage: Stage, message: str = "") -> None:
        self._stage = stage
        self._stage_frac = 0.0
        self._stage_has_detail = False
        self._emit(message, force=True)

    def update(self, fraction: float, message: str = "") -> None:
        if self._stage is None:
            return
        self._stage_frac = max(self._stage_frac, min(1.0, float(fraction)))
        self._stage_has_detail = True
        self._emit(message)

    def note(self, message: str) -> None:
        """Log an informational message (e.g. a rate-limit wait) without
        moving the progress bar."""
        if self._stage is None:
            return
        self._emit(message, force=True)

    def finish(self, message: str = "") -> None:
        if self._stage is None:
            return
        self._stage_frac = 1.0
        self._stage_has_detail = True
        self._emit(message, force=True)
        self._completed_weight += self._weights.get(self._stage, 0.0)
        self._stage = None


def _check_cancel(cancel_event) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise PipelineCancelled()


# ── FFmpeg helpers (burn-in) ──────────────────────────────────────────────
_subtitle_filter_cache: Dict[str, bool] = {}


def ffmpeg_candidates() -> List[str]:
    """Ordered candidate FFmpeg binaries (system first, imageio fallback)."""
    candidates: List[str] = []
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        candidates.append(system_ffmpeg)
    try:
        import imageio_ffmpeg

        candidates.append(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:  # noqa: BLE001
        pass
    seen, unique = set(), []
    for cand in candidates:
        if cand and cand not in seen and os.path.exists(cand):
            seen.add(cand)
            unique.append(cand)
    return unique


def _supports_subtitle_filter(ffmpeg: str) -> bool:
    cached = _subtitle_filter_cache.get(ffmpeg)
    if cached is not None:
        return cached
    ok = False
    try:
        proc = subprocess.run(
            [ffmpeg, "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        for line in (proc.stdout or "").splitlines():
            parts = line.split()
            if len(parts) >= 2 and "subtitles" in parts[:2]:
                ok = True
                break
    except Exception:  # noqa: BLE001
        ok = False
    _subtitle_filter_cache[ffmpeg] = ok
    return ok


def find_ffmpeg(require_subtitles: bool = False) -> Optional[str]:
    for cand in ffmpeg_candidates():
        if not require_subtitles or _supports_subtitle_filter(cand):
            return cand
    return None


def burn_status() -> dict:
    """Availability report for the ``/api/health`` endpoint."""
    ffmpeg = find_ffmpeg(require_subtitles=True)
    if ffmpeg:
        return {"available": True, "ffmpeg": ffmpeg, "reason": ""}
    if not ffmpeg_candidates():
        return {"available": False, "ffmpeg": "", "reason": "FFmpeg not found"}
    return {
        "available": False,
        "ffmpeg": "",
        "reason": "The available FFmpeg build lacks the 'subtitles' filter (libass)",
    }


def _escape_filter_path(path: str) -> str:
    """Escape a filename for use inside an FFmpeg filter argument."""
    normalized = str(os.path.abspath(path))
    if os.name == "nt":
        normalized = normalized.replace("\\", "/")
    escaped = "".join(f"\\{ch}" if ch in "\\':,[];" else ch for ch in normalized)
    return f"'{escaped}'"


def burn_subtitles(
    video_path: str,
    srt_path: str,
    output_path: str,
    duration: Optional[float] = None,
    on_progress: Optional[Callable[[float], None]] = None,
    cancel_event=None,
) -> str:
    """Burn the SRT into a copy of the video using FFmpeg + libass."""
    _check_cancel(cancel_event)
    ffmpeg = find_ffmpeg(require_subtitles=True)
    if not ffmpeg:
        raise RuntimeError(
            "No FFmpeg with the 'subtitles' filter is available for burn-in"
        )

    filter_arg = "subtitles=filename=" + _escape_filter_path(srt_path)
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-nostdin",
        "-progress", "pipe:1", "-nostats",
        "-i", video_path,
        "-vf", filter_arg,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]

    log_path = output_path + ".ffmpeg.log"
    with open(log_path, "wb") as err_handle:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=err_handle,
            stdin=subprocess.DEVNULL,
        )
        time_re = re.compile(r"^out_time=(\d+):(\d{2}):(\d{2}(?:\.\d+)?)")
        try:
            assert proc.stdout is not None
            for raw in proc.stdout:
                if cancel_event is not None and cancel_event.is_set():
                    _terminate(proc)
                    raise PipelineCancelled()
                line = raw.decode("utf-8", "replace").strip()
                match = time_re.match(line)
                if match and duration and on_progress:
                    seconds = (
                        int(match.group(1)) * 3600
                        + int(match.group(2)) * 60
                        + float(match.group(3))
                    )
                    on_progress(min(0.99, max(0.0, seconds / float(duration))))
            return_code = proc.wait()
        except BaseException:
            _terminate(proc)
            raise
        finally:
            if proc.poll() is None:  # safety net
                _terminate(proc)

    if return_code != 0:
        tail = _read_tail(log_path, 4000)
        raise RuntimeError(f"FFmpeg exited with code {return_code}: {tail}")
    try:
        os.remove(log_path)
    except OSError:
        pass
    if on_progress:
        on_progress(1.0)
    return output_path


def _terminate(proc: subprocess.Popen) -> None:
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:  # noqa: BLE001
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass


def _read_tail(path: str, max_bytes: int = 4000) -> str:
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes))
            return handle.read().decode("utf-8", "replace").strip()
    except OSError:
        return ""


# ── The pipeline ──────────────────────────────────────────────────────────
#: Resume caches (web jobs only — desktop passes cache_dir=None and keeps
#: its output folder clean).
TRANSCRIPT_CACHE_NAME = "transcript.json"
TRANSLATION_CACHE_NAME = "translations.json"
CACHE_VERSION = 1


def _load_cache_json(cache_dir: Optional[str], name: str) -> Optional[dict]:
    if not cache_dir:
        return None
    try:
        with open(os.path.join(cache_dir, name), "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("version") == CACHE_VERSION else None


def _save_cache_json(cache_dir: Optional[str], name: str, payload: dict) -> None:
    if not cache_dir:
        return
    path = os.path.join(cache_dir, name)
    tmp = path + ".tmp"
    try:
        os.makedirs(cache_dir, exist_ok=True)
        payload = {"version": CACHE_VERSION, **payload}
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        os.replace(tmp, path)
    except (OSError, TypeError, ValueError):
        try:
            os.remove(tmp)
        except OSError:
            pass


def _load_transcript_cache(cache_dir: Optional[str]) -> Optional[dict]:
    """Cached ``{language, duration, segments}`` from a previous attempt."""
    data = _load_cache_json(cache_dir, TRANSCRIPT_CACHE_NAME)
    if data is None:
        return None
    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        return None
    return data


def _save_transcript_cache(
    cache_dir: Optional[str],
    language: Optional[str],
    duration: Optional[float],
    segments: List[dict],
) -> None:
    _save_cache_json(
        cache_dir,
        TRANSCRIPT_CACHE_NAME,
        {"language": language, "duration": duration, "segments": segments},
    )


def _load_translation_cache(
    cache_dir: Optional[str], options: JobOptions, source: str
) -> Dict[str, str]:
    """Cached ``{source text → translation}`` — empty when mismatched."""
    data = _load_cache_json(cache_dir, TRANSLATION_CACHE_NAME)
    if data is None:
        return {}
    if (
        data.get("engine") != options.engine
        or data.get("target") != options.target_language
        or data.get("source") != (source or "")
    ):
        return {}
    out: Dict[str, str] = {}
    for pair in data.get("pairs") or []:
        if isinstance(pair, (list, tuple)) and len(pair) == 2 and pair[0] and isinstance(pair[1], str):
            out[str(pair[0])] = str(pair[1])
    return out


def _save_translation_cache(
    cache_dir: Optional[str], options: JobOptions, source: str, mapping: Dict[str, str]
) -> None:
    _save_cache_json(
        cache_dir,
        TRANSLATION_CACHE_NAME,
        {
            "engine": options.engine,
            "target": options.target_language,
            "source": source or "",
            "pairs": [[k, v] for k, v in mapping.items()],
        },
    )


def run_pipeline(
    media_path: str,
    output_dir: str,
    options: Optional[JobOptions] = None,
    *,
    base_name: Optional[str] = None,
    on_event: Optional[Callable[[ProgressEvent], None]] = None,
    cancel_event=None,
    progress_offset: float = 0.0,
    progress_scale: float = 100.0,
    cache_dir: Optional[str] = None,
) -> PipelineResult:
    """Run the full video → Arabic subtitles pipeline.

    ``progress_offset`` / ``progress_scale`` map the pipeline's internal
    0–100 % into an outer range (used for multi-file desktop batches and
    the web job's URL-download phase).

    ``cache_dir`` (web jobs) stores a transcript and partial translations so
    a failed/cancelled run can be retried without redoing the expensive
    stages: if ``transcript.json`` exists the extract+transcribe stages are
    skipped, and already-translated segments from ``translations.json`` are
    reused as-is.
    """
    options = options or JobOptions()
    os.makedirs(output_dir, exist_ok=True)
    stem = base_name or os.path.splitext(os.path.basename(media_path))[0]
    weights = _WEIGHTS_WITH_BURN if options.burn_video else _WEIGHTS_WITHOUT_BURN
    emitter = _Emitter(on_event, progress_offset, progress_scale, weights)

    warnings: List[str] = []
    files: Dict[str, str] = {}
    wav_path: Optional[str] = None
    cached = _load_transcript_cache(cache_dir)

    try:
        # ── Stages 1+2: extract audio + transcribe ─────────────────────
        _check_cancel(cancel_event)
        if cached is not None:
            emitter.start(Stage.EXTRACTING, "Extracting audio track…")
            duration = cached.get("duration")
            emitter.finish("Skipped — cached transcript found")
            emitter.start(Stage.TRANSCRIBING, "Transcribing speech to text…")
            segments = cached["segments"]
            language = cached.get("language") or options.source_language or "auto"
            emitter.update(1.0)
            emitter.finish(f"Reused cached transcript ({len(segments)} segment(s))")
        else:
            emitter.start(Stage.EXTRACTING, "Extracting audio track…")
            try:
                wav_path = audio_mod.extract_audio(media_path, output_dir, cancel_event=cancel_event)
            except PipelineCancelled:
                raise
            except Exception as exc:  # noqa: BLE001
                raise StageError(Stage.EXTRACTING, str(exc), exc) from exc
            duration = audio_mod.probe_duration(wav_path)
            emitter.finish("Audio extracted")

            _check_cancel(cancel_event)
            emitter.start(Stage.TRANSCRIBING, "Transcribing speech to text…")
            try:
                result = transcribe_mod.transcribe(
                    wav_path,
                    model_size=options.model_size,
                    language=options.source_language,
                    on_progress=lambda f: emitter.update(f),
                    cancel_event=cancel_event,
                )
            except PipelineCancelled:
                raise
            except Exception as exc:  # noqa: BLE001
                raise StageError(Stage.TRANSCRIBING, str(exc), exc) from exc
            segments = result["segments"]
            language = result.get("language") or options.source_language or "auto"
            emitter.finish(f"Transcribed {len(segments)} segment(s)")
            _save_transcript_cache(cache_dir, language, duration, segments)

        # ── Stage 3: translate ─────────────────────────────────────────
        _check_cancel(cancel_event)
        texts = [str(seg.get("text", "")).strip() for seg in segments]
        passthrough = options.engine in ("none", "skip", "off") or (
            language or ""
        ).lower() == options.target_language
        known: Dict[str, str] = (
            {} if passthrough else _load_translation_cache(cache_dir, options, language)
        )
        persist: Dict[str, str] = dict(known)
        if known:
            emitter.start(
                Stage.TRANSLATING,
                f"Translating to Arabic… resuming with {len(known)} cached segment(s)",
            )
        else:
            emitter.start(Stage.TRANSLATING, "Translating to Arabic…")

        def _on_batch(chunk, values) -> None:
            for src, dst in zip(chunk, values):
                persist[str(src)] = str(dst)
            _save_translation_cache(cache_dir, options, language, persist)

        try:
            translated = translate_mod.translate_batch(
                texts,
                source=language,
                target=options.target_language,
                engine=options.engine,
                on_progress=lambda f: emitter.update(f),
                cancel_event=cancel_event,
                known=known,
                on_batch=_on_batch,
                on_note=emitter.note,
            )
        except PipelineCancelled:
            raise
        except Exception as exc:  # noqa: BLE001
            raise StageError(Stage.TRANSLATING, str(exc), exc) from exc
        if not passthrough:
            for src, dst in zip(texts, translated):
                if src and dst:
                    persist[str(src)] = str(dst)
            if persist:
                _save_translation_cache(cache_dir, options, language, persist)
        emitter.finish("Translation complete")

        # ── Stage 4: generate subtitle files ──────────────────────────
        _check_cancel(cancel_event)
        emitter.start(Stage.GENERATING, "Generating subtitle files…")
        try:
            cues = subtitles.cues_from_segments(segments, translated)
            for fmt in options.wanted_formats():
                out_path = os.path.join(output_dir, f"{stem}.{fmt}")
                subtitles.write_file(cues, out_path, fmt=fmt, bom=options.add_bom)
                files[fmt] = out_path
        except PipelineCancelled:
            raise
        except Exception as exc:  # noqa: BLE001
            raise StageError(Stage.GENERATING, str(exc), exc) from exc
        emitter.finish(f"Generated {', '.join(files)}")
    finally:
        # The extracted WAV is never needed again (matches desktop behavior).
        _remove_quiet(wav_path)

    # ── Stage 5 (optional): burn subtitles into the video ─────────────
    if options.burn_video:
        _check_cancel(cancel_event)
        emitter.start(Stage.BURNING, "Burning subtitles into the video…")
        srt_path = files.get("srt") or subtitles.write_file(
            cues, os.path.join(output_dir, f"{stem}.srt"), "srt", options.add_bom
        )
        files.setdefault("srt", srt_path)
        video_out = os.path.join(output_dir, f"{stem}.subtitled.mp4")
        try:
            burn_subtitles(
                media_path,
                srt_path,
                video_out,
                duration=duration,
                on_progress=lambda f: emitter.update(f),
                cancel_event=cancel_event,
            )
            files["video"] = video_out
        except PipelineCancelled:
            raise
        except Exception as exc:  # noqa: BLE001 — non-fatal: subs are already on disk
            warnings.append(f"Burn-in failed: {exc}")
        emitter.finish("Burn-in complete" if "video" in files else "Burn-in skipped")

    return PipelineResult(
        cues=cues,
        language=language,
        duration=duration,
        files=files,
        warnings=warnings,
    )


def _remove_quiet(path: Optional[str]) -> None:
    if not path:
        return
    try:
        os.remove(path)
    except OSError:
        pass
