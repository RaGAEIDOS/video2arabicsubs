"""Audio extraction from video files (moviepy), plus duration probing.

Heavy imports are intentionally lazy so that merely importing the web
server does not require moviepy/torch to be installed.
"""
from __future__ import annotations

import os
import wave
from typing import Optional

from core.models import PipelineCancelled


def _check_cancel(cancel_event) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise PipelineCancelled()


def _import_video_file_clip():
    try:  # moviepy >= 2.0
        from moviepy import VideoFileClip
    except ImportError:  # moviepy 1.x
        from moviepy.editor import VideoFileClip  # type: ignore
    return VideoFileClip


def extract_audio(video_path: str, output_dir: Optional[str] = None, cancel_event=None) -> str:
    """Extract the audio track of ``video_path`` into a 16-bit WAV file.

    Returns the path of the written WAV file.
    """
    _check_cancel(cancel_event)

    video_name = os.path.splitext(os.path.basename(video_path))[0]
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        audio_path = os.path.join(output_dir, f"{video_name}.wav")
    else:
        audio_path = f"{video_name}.wav"

    VideoFileClip = _import_video_file_clip()
    with VideoFileClip(video_path) as video:
        if video.audio is None:
            raise ValueError("The file has no audio track")
        _check_cancel(cancel_event)
        video.audio.write_audiofile(audio_path, codec="pcm_s16le", logger=None)
    _check_cancel(cancel_event)
    return audio_path


def probe_duration(path: str) -> Optional[float]:
    """Best-effort duration (seconds) of a media file, ``None`` if unknown."""
    # Fast path: stdlib wave reader (works for the WAV files we produce).
    if path.lower().endswith(".wav"):
        try:
            with wave.open(path, "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate:
                    return frames / float(rate)
        except Exception:
            pass
    # Fallback: moviepy (already a dependency of the project).
    try:
        VideoFileClip = _import_video_file_clip()
        with VideoFileClip(path) as clip:
            if clip.duration:
                return float(clip.duration)
    except Exception:
        pass
    return None
