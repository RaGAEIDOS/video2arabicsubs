"""Arabic display shaping for Tkinter — fixes disconnected letters.

Tcl/Tk 8.6 on Linux/X11 has **no complex-text shaping engine** (no
HarfBuzz), so Arabic text paints one glyph per letter in its *isolated*
form — letters appear disconnected and words read scrambled. Windows Tk
shapes through Uniscribe and macOS Tk through CoreText, both correctly —
so this only matters on Linux.

This module pre-shapes strings **at the Tk display boundary**:

* ``arabic-reshaper`` — contextual letter forms (isolated / initial /
  medial / final) plus the mandatory lam-alef ligatures,
* ``python-bidi`` — the Unicode bidirectional algorithm (visual RTL
  reordering, mixed Arabic + Latin/digits/URL runs, bracket handling).

Rules enforced by the surrounding code:

* Shape **only** text rendered *inside* Tk widgets (``text=``,
  ``StringVar`` values for labels, ``Text.insert``).
* Never shape: window-manager titles (``root.title``, dialog ``title=``,
  rendered by the WM with its own shaper), system-tray menus (rendered by
  GTK/Qt), nor any text on disk (``.srt`` / ``.vtt``, log files) — those
  stay in logical order for players and tools.
* Single-pass only: ``shaped()`` is **not idempotent** (re-running bidi
  on visual text would un-reorder it) — always call it with logical text.

If the optional packages are missing the function degrades to a
transparent pass-through, and it is a no-op on Windows/macOS and on
Tk 8.7+ (which ships HarfBuzz).
"""
from __future__ import annotations

import sys

# ── optional dependencies ───────────────────────────────────────────────────
try:  # pragma: no cover - availability depends on the environment
    import arabic_reshaper as _reshaper
except Exception:  # pragma: no cover
    _reshaper = None

try:  # pragma: no cover
    try:
        from bidi.algorithm import get_display as _get_display
    except ImportError:  # newer python-bidi layouts
        from bidi import get_display as _get_display
except Exception:  # pragma: no cover
    _get_display = None


def available() -> bool:
    """True when both shaping libraries imported successfully."""
    return _reshaper is not None and _get_display is not None


def _native_shaping() -> bool:
    """True on platforms whose Tk already shapes complex scripts."""
    if not sys.platform.startswith("linux"):
        return True  # Windows (Uniscribe) / macOS (CoreText)
    try:
        import tkinter
        return tkinter.TkVersion >= 8.7  # 8.7+ bundles HarfBuzz
    except Exception:
        return False


#: Master switch — used by the UI and asserted by the tests.
ENABLED = available() and not _native_shaping()


def shaped(text: str) -> str:
    """Return ``text`` ready to paint in a Tk widget (logical → visual).

    Latin-only strings come back unchanged, so it is safe to wrap every
    label unconditionally. On unsupported platforms or when the optional
    libraries are absent this is a pass-through.
    """
    if not ENABLED or not text:
        return text
    try:
        return _get_display(_reshaper.reshape(text))
    except Exception:  # never break the UI over cosmetics
        return text
