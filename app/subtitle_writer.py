"""Backward-compatible wrapper — the implementation lives in ``core.subtitles``."""
from core import subtitles as _subtitles
from core.subtitles import format_timestamp as _format_time  # noqa: F401


def write_srt(segments, translated_texts, output_path):
    cues = _subtitles.cues_from_segments(segments, translated_texts)
    return _subtitles.write_file(cues, output_path, fmt="srt")
