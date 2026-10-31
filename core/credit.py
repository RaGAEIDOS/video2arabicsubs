"""Promotional credit cue appended to every translated subtitle file.

The credit is added as a **visible final cue** (~4 seconds, aligned with the
end of the video when the duration is known) so viewers of the finished
video/subtitles see who made the tool — and it is also burned into the video
automatically when burn-in is enabled (it is just another SRT cue).

It is a standalone module (one macro = one goal) so the pipeline, the web
API and any future UI can reuse the exact same logic.
"""
from __future__ import annotations

from typing import List, Optional, Sequence

from core.models import Cue

#: The exact credit text requested for the project.
CREDIT_TEXT = "تم الترجمة بواسطة https://github.com/RaGAEIDOS/video2arabicsubs"

#: How long the credit stays on screen (seconds).
CREDIT_HOLD_SECONDS = 4.0

#: Gap between the last cue and the credit when no duration is known.
CREDIT_GAP_SECONDS = 0.25

#: Minimum sensible length for the credit cue when aligning to the end.
MIN_CREDIT_SPAN = 1.0


def credit_cue(
    duration: Optional[float] = None,
    last_end: float = 0.0,
    hold: float = CREDIT_HOLD_SECONDS,
) -> Cue:
    """Build the credit cue positioned at the end of the video.

    * duration known → the cue occupies the final ``hold`` seconds of the
      video (so it is visible while watching / burning),
    * otherwise → it starts just after the last cue.
    """
    hold = max(1.0, float(hold))
    last_end = max(0.0, float(last_end))
    if duration and float(duration) > 0 and last_end < float(duration):
        duration = float(duration)
        start = max(last_end, duration - hold)
        end = min(start + hold, duration)
        if end - start < MIN_CREDIT_SPAN:
            # Very short tail (e.g. last cue ends right at the video end):
            # pull the cue back so it keeps a readable minimum length.
            start = max(0.0, duration - max(hold, MIN_CREDIT_SPAN))
            end = duration
    else:
        start = last_end + CREDIT_GAP_SECONDS
        end = start + hold
    return Cue(index=0, start=start, end=end, text=CREDIT_TEXT)


def append_credit(
    cues: Sequence[Cue],
    duration: Optional[float] = None,
    hold: float = CREDIT_HOLD_SECONDS,
) -> List[Cue]:
    """Return a copy of ``cues`` with the credit appended as the last cue.

    Indices are renumbered sequentially, so SRT/VTT output stays contiguous.
    Empty subtitle lists are returned untouched (no credit without content).
    """
    out: List[Cue] = [Cue(index=i + 1, start=c.start, end=c.end, text=c.text)
                      for i, c in enumerate(cues)]
    if not out:
        return out
    last_end = max(c.end for c in out)
    credit = credit_cue(duration=duration, last_end=last_end, hold=hold)
    credit.index = len(out) + 1
    out.append(credit)
    return out


def apply_credit(
    cues: Sequence[Cue],
    duration: Optional[float] = None,
    enabled: bool = True,
    hold: float = CREDIT_HOLD_SECONDS,
) -> List[Cue]:
    """Convenience wrapper honouring the user's on/off toggle."""
    if not enabled:
        return list(cues)
    return append_credit(cues, duration=duration, hold=hold)
