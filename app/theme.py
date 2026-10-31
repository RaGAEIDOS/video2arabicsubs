"""M6 macro — the visual identity of the desktop app (colors, fonts, motion).

A single, opinionated **modern dark theme** (Slate + Indigo/Violet gradient)
that mirrors the web UI, so the product looks the same everywhere. Everything
is plain data — :mod:`app.widgets` and :mod:`app.gui` only read from here.

Also centralises the **motion** timings used by the animated widgets, plus a
tiny color-lerp helper so entrance animations can interpolate between shades.
"""
from __future__ import annotations

from typing import Tuple

# ── Palette ───────────────────────────────────────────────────────────────
BG          = "#0b1020"   # app background (near-black indigo)
SURFACE     = "#131a2e"   # card surface
SURFACE_HI  = "#1b2440"   # raised / hovered surface
BORDER      = "#25304d"   # hairline borders
BORDER_HI   = "#3b4a75"   # focused borders

TEXT        = "#e7ecf7"   # primary text
TEXT_DIM    = "#94a3c4"   # secondary text
TEXT_FAINT  = "#5f6d90"   # tertiary / hints

ACCENT      = "#6366f1"   # indigo-500 (primary)
ACCENT_HI    = "#818cf8"  # indigo-400 (hover)
ACCENT_DEEP  = "#4f46e5"  # indigo-600 (pressed)
ACCENT_2     = "#a855f7"  # violet-500 (gradient partner)

SUCCESS     = "#22c55e"
SUCCESS_DIM = "#166534"
WARN        = "#f59e0b"
DANGER      = "#ef4444"
DANGER_DEEP = "#b91c1c"

TRACK       = "#1e2742"   # progress-bar track
SHIMMER     = "#ffffff"   # progress-bar shimmer highlight

# ── Fonts ─────────────────────────────────────────────────────────────────
# Try to pick a font that renders Arabic + Latin nicely, in priority order.
FONT_FAMILIES = ("Segoe UI", "Cairo", "Noto Sans Arabic", "DejaVu Sans", "TkDefaultFont")
FONT_MONO = ("Consolas", "DejaVu Sans Mono", "monospace")

FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_CARD = ("Segoe UI", 12, "bold")
FONT_BODY = ("Segoe UI", 11)
FONT_SMALL = ("Segoe UI", 9)
FONT_TINY = ("Segoe UI", 8)
FONT_NUM = ("Consolas", 11, "bold")

# ── Geometry / motion ─────────────────────────────────────────────────────
RADIUS = 12            # card corner radius (px)
RADIUS_SM = 8          # small controls radius
PAD = 14               # inner card padding
GAP = 12               # vertical gap between cards

# Animation timings (milliseconds) — kept short so the UI feels snappy.
ANIM_FAST = 90         # hover / press color transitions
ANIM_SLIDE = 160       # segmented-control indicator slide
ANIM_PROGRESS = 120    # progress bar smoothing
ANIM_ENTER = 260       # card entrance (fade/slide)
ANIM_PULSE = 1400      # "working" pulse loop

FPS_MS = 16            # ~60 fps ticker for the animated widgets


def hex_to_rgb(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    r, g, b = (max(0, min(255, int(round(c)))) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def lerp_color(a: str, b: str, t: float) -> str:
    """Linear interpolate between two hex colors (t in 0..1)."""
    t = max(0.0, min(1.0, float(t)))
    ra, ga, ba = hex_to_rgb(a)
    rb, gb, bb = hex_to_rgb(b)
    return rgb_to_hex((ra + (rb - ra) * t, ga + (gb - ga) * t, ba + (bb - ba) * t))


def shade(color: str, amount: float) -> str:
    """Darken (amount<0) or lighten (amount>0) a hex color."""
    return lerp_color(color, "#ffffff" if amount >= 0 else "#000000", abs(amount))


def supports_rgba() -> bool:
    """True when the platform Tk supports alpha (used for soft shadows)."""
    import tkinter as tk

    try:
        root = tk._default_root
        if root is None:
            return False
        return bool(root.winfo_rgb("#000000"))
    except Exception:  # noqa: BLE001
        return False
