"""Shared data models for the Video2ArabicSubs engine.

This module (and everything under ``core``) is completely decoupled from
the Tkinter GUI *and* from the web layer — it only depends on the stdlib.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Stages ────────────────────────────────────────────────────────────────
class Stage(str, Enum):
    """Pipeline/job stages, ordered as they happen."""

    QUEUED = "queued"
    DOWNLOADING = "downloading"
    EXTRACTING = "extracting"
    TRANSCRIBING = "transcribing"
    TRANSLATING = "translating"
    GENERATING = "generating"
    BURNING = "burning"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


TERMINAL_STAGES = frozenset({Stage.DONE, Stage.ERROR, Stage.CANCELLED})


# ── Exceptions ────────────────────────────────────────────────────────────
class PipelineCancelled(Exception):
    """Raised when the user requested cancellation of a running job."""


class StageError(Exception):
    """Wraps an exception raised inside a specific pipeline stage."""

    def __init__(self, stage: Stage, message: str, cause: Optional[BaseException] = None):
        super().__init__(message)
        self.stage = stage
        self.message = message
        self.cause = cause

    def traceback_text(self) -> str:
        import traceback

        if self.cause is not None:
            return "".join(
                traceback.format_exception(
                    type(self.cause), self.cause, self.cause.__traceback__
                )
            )
        return "".join(traceback.format_exception(type(self), self, self.__traceback__))


# ── Subtitle cue ──────────────────────────────────────────────────────────
@dataclass
class Cue:
    """A single subtitle cue with times in seconds."""

    index: int
    start: float
    end: float
    text: str

    def to_dict(self) -> Dict[str, Any]:
        return {"index": self.index, "start": self.start, "end": self.end, "text": self.text}


# ── Progress event ────────────────────────────────────────────────────────
@dataclass
class ProgressEvent:
    """Structured progress update emitted by the pipeline."""

    stage: Stage
    percent: float                 # overall 0..100 for the whole job
    stage_percent: Optional[float]  # 0..1 within the stage, None if unknown
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "progress",
            "stage": self.stage.value,
            "percent": round(self.percent, 1),
            "stage_percent": None if self.stage_percent is None else round(self.stage_percent, 4),
            "message": self.message,
        }


# ── Job options ───────────────────────────────────────────────────────────
MODEL_SIZES = ("tiny", "base", "small", "medium", "large", "turbo")
ENGINES = ("google", "argos", "none")
OUTPUT_FORMATS = ("srt", "vtt", "both")

#: Curated subset of Whisper languages (ISO-639-1) for the UI dropdown.
LANGUAGES: Dict[str, str] = {
    "auto": "Auto-detect",
    "en": "English",
    "ar": "Arabic",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "tr": "Turkish",
    "ur": "Urdu",
    "fa": "Persian",
    "id": "Indonesian",
    "hi": "Hindi",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "nl": "Dutch",
    "pl": "Polish",
    "sv": "Swedish",
    "uk": "Ukrainian",
}

_LANG_CODE_RE = re.compile(r"^[a-z]{2,3}(-[a-z]+)?$")


@dataclass
class JobOptions:
    """Processing options for one video (shared by desktop and web)."""

    model_size: str = "small"
    source_language: str = "auto"      # "auto" or ISO-639-1 code
    engine: str = "google"             # "google" (falls back offline) | "argos" | "none"
    output_format: str = "both"        # "srt" | "vtt" | "both"
    burn_video: bool = False           # burn subtitles into a copy of the video
    add_bom: bool = False              # write files as UTF-8 with BOM
    target_language: str = "ar"

    def __post_init__(self) -> None:
        if self.model_size not in MODEL_SIZES:
            raise ValueError(f"Invalid model_size: {self.model_size!r}")
        if self.engine not in ENGINES:
            raise ValueError(f"Invalid engine: {self.engine!r}")
        if self.output_format not in OUTPUT_FORMATS:
            raise ValueError(f"Invalid output_format: {self.output_format!r}")
        lang = (self.source_language or "auto").strip().lower()
        if lang != "auto" and not _LANG_CODE_RE.match(lang):
            raise ValueError(f"Invalid source_language: {self.source_language!r}")
        self.source_language = lang

    def wanted_formats(self) -> List[str]:
        """Formats to write to disk (burn-in always needs an SRT)."""
        if self.output_format == "both":
            return ["srt", "vtt"]
        formats = [self.output_format]
        if self.burn_video and "srt" not in formats:
            formats.append("srt")
        return formats

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_size": self.model_size,
            "source_language": self.source_language,
            "engine": self.engine,
            "output_format": self.output_format,
            "burn_video": self.burn_video,
            "add_bom": self.add_bom,
            "target_language": self.target_language,
        }
