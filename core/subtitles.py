"""Subtitle serialization: SRT and WebVTT, always UTF-8.

* ``serialize`` builds text from cues (re-indexed sequentially),
* ``write_file`` writes with ``utf-8`` or ``utf-8-sig`` (BOM for stubborn
  Windows players),
* ``parse`` reads both SRT and WebVTT back into cues (used by the web editor
  round-trip).

Timestamp formatting rounds to whole milliseconds *before* decomposing,
avoiding the ``00:00:60,000`` glitch of naive truncation.
"""
from __future__ import annotations

import re
from typing import List, Sequence

from core.models import Cue

_TIMING_LINE_RE = re.compile(
    r"(?P<start>(?:\d{1,2}:)?\d{1,2}:\d{2}[,.]\d{1,3})\s*-->\s*"
    r"(?P<end>(?:\d{1,2}:)?\d{1,2}:\d{2}[,.]\d{1,3})"
)
_TIMESTAMP_RE = re.compile(r"^(?:(\d{1,2}):)?(\d{1,2}):(\d{1,2})[,.](\d{1,3})$")


def format_timestamp(seconds: float, separator: str = ",") -> str:
    """``123.456`` → ``00:02:03,456`` (``separator='.'`` for WebVTT)."""
    total_ms = max(0, int(round(float(seconds) * 1000)))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d}{separator}{ms:03d}"


def parse_timestamp(value: str) -> float:
    """``00:02:03,456`` / ``00:02:03.456`` / ``02:03.456`` → seconds."""
    match = _TIMESTAMP_RE.match(value.strip())
    if not match:
        raise ValueError(f"Invalid timestamp: {value!r}")
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    millis = int(match.group(4).ljust(3, "0"))
    if seconds > 59 or minutes > 59:
        raise ValueError(f"Invalid timestamp: {value!r}")
    return hours * 3600 + minutes * 60 + seconds + millis / 1000.0


def cues_from_segments(segments: Sequence[dict], translations: Sequence[str] = ()) -> List[Cue]:
    """Build cues from Whisper segments + (optional) translated texts.

    Empty results are skipped and indices are assigned sequentially, so the
    final SRT is always contiguous — even when some segments had no text or
    translation.
    """
    cues: List[Cue] = []
    for i, seg in enumerate(segments):
        original = str(seg.get("text", "")).strip()
        translated = ""
        if i < len(translations):
            translated = str(translations[i] or "").strip()
        text = translated or original
        if not text:
            continue
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))
        if end < start:
            end = start
        cues.append(Cue(index=len(cues) + 1, start=start, end=end, text=text))
    return cues


def serialize(cues: Sequence[Cue], fmt: str = "srt") -> str:
    """Render cues as SRT or WebVTT text (str — encode as UTF-8 on write)."""
    if fmt not in ("srt", "vtt"):
        raise ValueError(f"Unsupported subtitle format: {fmt!r}")
    separator = "." if fmt == "vtt" else ","
    lines: List[str] = []
    if fmt == "vtt":
        lines.append("WEBVTT")
        lines.append("")
    for i, cue in enumerate(cues, start=1):
        if fmt == "srt":
            lines.append(str(i))
        lines.append(
            f"{format_timestamp(cue.start, separator)} --> "
            f"{format_timestamp(cue.end, separator)}"
        )
        lines.append(cue.text.strip() or "")
        lines.append("")
    return "\n".join(lines)


def write_file(cues: Sequence[Cue], path: str, fmt: str = "srt", bom: bool = False) -> str:
    """Write cues to ``path`` as UTF-8 (``utf-8-sig`` when ``bom`` is set)."""
    text = serialize(cues, fmt)
    encoding = "utf-8-sig" if bom else "utf-8"
    with open(path, "w", encoding=encoding, newline="\n") as handle:
        handle.write(text)
    return path


def parse(text: str) -> List[Cue]:
    """Parse SRT *or* WebVTT text into cues (tolerant, used by the editor)."""
    if text.startswith("\ufeff"):
        text = text[1:]
    cues: List[Cue] = []
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n"))
    for block in blocks:
        lines = [ln for ln in block.split("\n")]
        # Drop leading numeric index (SRT) or "WEBVTT" header / NOTE blocks.
        timing_idx = None
        match = None
        for i, line in enumerate(lines):
            m = _TIMING_LINE_RE.search(line)
            if m:
                timing_idx, match = i, m
                break
        if timing_idx is None or match is None:
            continue
        try:
            start = parse_timestamp(match.group("start"))
            end = parse_timestamp(match.group("end"))
        except ValueError:
            continue
        # Remove any trailing VTT settings (e.g. "align:start") after "-->".
        body_lines = lines[timing_idx + 1 :]
        body = "\n".join(body_lines).strip("\n")
        if not body.strip():
            continue
        cues.append(Cue(index=len(cues) + 1, start=start, end=end, text=body.strip()))
    return cues
