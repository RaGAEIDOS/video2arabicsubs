"""M7 macro — animated, modern Tkinter widgets (the “no-lag” building blocks).

Everything here is self-contained: each widget owns a tiny animation loop
scheduled with ``root.after`` and **cancels it on destroy**, so nothing leaks
or keeps the event loop busy when the window closes (no ghost timers, no
``update()``-spinning — the historical cause of Tk “hanging”).

Widgets provided
----------------
* :class:`Card`              — rounded panel with a title + optional entrance fade
* :class:`ModernButton`      — rounded button with hover/press color transitions
* :class:`Switch`            — animated on/off toggle (knob slides)
* :class:`SegmentedControl`  — radio group with a sliding indicator
* :class:`AnimatedProgress`  — smooth progress bar with a sweeping shimmer
* :class:`Badge`             — small pill label (status chips)

All colors/fonts come from :mod:`app.theme`; no widget hard-codes a style.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable, List, Optional, Sequence

from app import theme


# ── helpers ───────────────────────────────────────────────────────────────
def _bg_of(widget) -> str:
    """Best-effort background color of a widget's parent."""
    try:
        return widget.cget("bg")
    except Exception:  # noqa: BLE001
        return theme.BG


def rounded_rect(canvas: "tk.Canvas", x1, y1, x2, y2, r, **kw):
    """Draw a rounded rectangle on a Tk Canvas (Tk 8.6 has no native rounded
    shapes — this is the classic smooth-polygon trick)."""
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kw)


class _Loop:
    """Minimal per-widget animation scheduler that cleans itself up."""

    def __init__(self, widget, tick: Callable[[float], bool], fps_ms=theme.FPS_MS):
        self._widget = widget
        self._tick = tick          # returns True while it wants more frames
        self._after = None
        self._fps = fps_ms
        widget.bind("<Destroy>", self._on_destroy, add="+")

    def start(self) -> None:
        if self._after is None and self._widget.winfo_exists():
            self._after = self._widget.after(self._fps, self._frame)

    def _frame(self) -> None:
        self._after = None
        if not self._widget.winfo_exists():
            return
        try:
            more = self._tick()
        except tk.TclError:
            return
        if more and self._widget.winfo_exists():
            self._after = self._widget.after(self._fps, self._frame)

    def _on_destroy(self, event) -> None:
        if event.widget is self._widget and self._after is not None:
            try:
                self._widget.after_cancel(self._after)
            except Exception:  # noqa: BLE001
                pass
            self._after = None


def animate_value(widget, getter: Callable[[], float], setter: Callable[[float], None],
                  target: float, duration_ms: int, on_done: Optional[Callable] = None):
    """Smoothly tween a numeric value from its current to ``target``."""
    start = getter()
    delta = target - start
    if abs(delta) < 1e-6:
        setter(target)
        if on_done:
            on_done()
        return
    steps = max(1, duration_ms // theme.FPS_MS)
    state = {"i": 0}

    def tick() -> bool:
        state["i"] += 1
        t = state["i"] / steps
        if t >= 1.0:
            setter(target)
            if on_done:
                on_done()
            return False
        # ease-out cubic
        eased = 1 - (1 - t) ** 3
        setter(start + delta * eased)
        return True

    _Loop(widget, tick).start()


# ── Card ──────────────────────────────────────────────────────────────────
class Card(tk.Frame):
    """A rounded surface panel with an optional title bar."""

    def __init__(self, parent, title: str = "", icon: str = "",
                 pad: int = theme.PAD, accent: bool = False, animate: bool = True):
        bg = _bg_of(parent)
        super().__init__(parent, bg=bg, highlightthickness=0)
        self._pad = pad
        self._accent = accent
        self._radius = theme.RADIUS
        self._h = 0

        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self.body = tk.Frame(self.canvas, bg=theme.SURFACE)
        self._icon = icon
        self._title_var = tk.StringVar(value=self._compose_title(title))
        self._title_lbl = tk.Label(self.body, textvariable=self._title_var,
                                   bg=theme.SURFACE,
                                   fg=theme.ACCENT_HI if accent else theme.TEXT,
                                   font=theme.FONT_CARD, anchor="w", justify="left")
        self._title_lbl.pack(fill="x", padx=pad, pady=(pad, 2))
        self._sep = tk.Frame(self.body, bg=theme.BORDER, height=1)
        self._sep.pack(fill="x", padx=pad, pady=(2, max(6, pad // 2)))

        self._body_win = self.canvas.create_window(pad, pad, anchor="nw", window=self.body)

        self.canvas.bind("<Configure>", self._redraw)
        self.body.bind("<Configure>", self._on_body_configure)

        self._fade = 0.0 if animate else 1.0
        if animate:
            self._run_enter()

    def _compose_title(self, title: str) -> str:
        return f"{self._icon}  {title}".strip() if title else ""

    def set_title(self, title: str, icon: str = None) -> None:
        if icon is not None:
            self._icon = icon
        self._title_var.set(self._compose_title(title))

    def _on_body_configure(self, _event=None) -> None:
        want = self.body.winfo_reqheight() + 2 * self._pad
        if abs(want - self._h) > 1:
            self._h = want
            try:
                self.canvas.configure(height=want)
            except tk.TclError:
                pass

    def _redraw(self, event=None) -> None:
        try:
            w = self.canvas.winfo_width()
            h = max(self.canvas.winfo_height(), self._h)
        except tk.TclError:
            return
        if w <= 1:
            return
        self.canvas.delete("bgshape")
        # entrance fade interpolates the surface color from the app bg.
        surface = theme.lerp_color(_bg_of(self), theme.SURFACE, self._fade)
        border = theme.lerp_color(_bg_of(self), theme.BORDER, self._fade)
        rounded_rect(self.canvas, 0, 0, w - 1, h - 1, self._radius,
                     fill=surface, outline=border, width=1)
        if self._accent:
            # thin accent bar down the start edge (mirrors for RTL via gui)
            rounded_rect(self.canvas, 0, 6, 4, h - 7, 2, fill=theme.ACCENT, outline="")
        self.canvas.tag_lower("bgshape")
        self.canvas.coords(self._body_win, self._pad, self._pad)
        try:
            self.canvas.itemconfigure(self._body_win, width=max(10, w - 2 * self._pad))
        except tk.TclError:
            pass
        # keep the title/sep colors in sync with the fade
        fg = theme.lerp_color(_bg_of(self), theme.ACCENT_HI if self._accent else theme.TEXT,
                              self._fade)
        try:
            self._title_lbl.configure(fg=fg, bg=surface)
            self._sep.configure(bg=border)
            self.body.configure(bg=surface)
        except tk.TclError:
            pass

    def _run_enter(self) -> None:
        def tick() -> bool:
            self._fade = min(1.0, self._fade + theme.FPS_MS / theme.ANIM_ENTER)
            self._redraw()
            return self._fade < 1.0

        _Loop(self, tick).start()

    # content helpers -----------------------------------------------------
    def add_label(self, text="", **kw) -> tk.Label:
        kw.setdefault("bg", theme.SURFACE)
        kw.setdefault("fg", theme.TEXT)
        kw.setdefault("font", theme.FONT_BODY)
        kw.setdefault("anchor", "w")
        lbl = tk.Label(self.body, text=text, **kw)
        return lbl


# ── ModernButton ──────────────────────────────────────────────────────────
class ModernButton(tk.Frame):
    """Rounded button with hover/press color animation and a disabled state."""

    def __init__(self, parent, text: str = "", command: Optional[Callable] = None,
                 kind: str = "primary", pad_x: int = 18, pad_y: int = 9,
                 state: str = "normal"):
        super().__init__(parent, bg=_bg_of(parent), highlightthickness=0)
        self._text = text
        self._command = command
        self._kind = kind
        self._pad_x = pad_x
        self._pad_y = pad_y
        self._state = state
        self._hover = 0.0
        self._press = 0.0

        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0,
                                bg=_bg_of(parent), cursor="hand2")
        self.canvas.pack()
        self._label = tk.Label(self.canvas, text=self._text, bg=theme.ACCENT,
                               fg="#ffffff", font=theme.FONT_BODY)
        self._win = self.canvas.create_window(0, 0, anchor="center", window=self._label)

        self._label.bind("<Enter>", self._on_enter)
        self._label.bind("<Leave>", self._on_leave)
        self._label.bind("<ButtonPress-1>", self._on_press)
        self._label.bind("<ButtonRelease-1>", self._on_release)
        for w in (self.canvas, self):
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

        self.canvas.bind("<Configure>", self._redraw)
        self._label.bind("<Configure>", self._on_label)
        self._apply_state_colors()

    # colors --------------------------------------------------------------
    def _palette(self):
        if self._kind == "primary":
            base, hover, press = theme.ACCENT, theme.ACCENT_HI, theme.ACCENT_DEEP
            fg = "#ffffff"
        elif self._kind == "danger":
            base, hover, press = theme.DANGER, theme.shade(theme.DANGER, 0.12), theme.DANGER_DEEP
            fg = "#ffffff"
        else:  # ghost
            base, hover, press = theme.SURFACE_HI, theme.BORDER_HI, theme.BORDER
            fg = theme.TEXT
        return base, hover, press, fg

    def _apply_state_colors(self) -> None:
        base, hover, press, fg = self._palette()
        if self._state == "disabled":
            base, fg = theme.SURFACE_HI, theme.TEXT_FAINT
        color = theme.lerp_color(base, press, self._press)
        color = theme.lerp_color(color, hover, self._hover)
        try:
            self._label.configure(bg=color, fg=fg)
        except tk.TclError:
            pass

    def _on_label(self, _e=None) -> None:
        self.canvas.configure(width=self._label.winfo_reqwidth() + 2 * self._pad_x,
                              height=self._label.winfo_reqheight() + 2 * self._pad_y)
        self._redraw()

    def _redraw(self, _e=None) -> None:
        try:
            w = self.canvas.winfo_width()
            h = self.canvas.winfo_height()
        except tk.TclError:
            return
        if w <= 1 or h <= 1:
            return
        self.canvas.delete("sh")
        rounded_rect(self.canvas, 0, 0, w - 1, h - 1, theme.RADIUS_SM,
                     fill="", outline="")
        self.canvas.coords(self._win, w / 2, h / 2)

    def _tween(self, attr: str, target: float) -> None:
        def tick() -> bool:
            cur = getattr(self, attr)
            step = (theme.FPS_MS / theme.ANIM_FAST)
            if cur < target:
                setattr(self, attr, min(target, cur + step))
            else:
                setattr(self, attr, max(target, cur - step))
            self._apply_state_colors()
            return abs(getattr(self, attr) - target) > 1e-3

        _Loop(self, tick).start()

    def _on_enter(self, _e=None):
        if self._state == "normal":
            self._tween("_hover", 1.0)

    def _on_leave(self, _e=None):
        self._tween("_hover", 0.0)
        self._tween("_press", 0.0)

    def _on_press(self, _e=None):
        if self._state == "normal":
            self._tween("_press", 1.0)

    def _on_release(self, _e=None):
        self._tween("_press", 0.0)
        if self._state == "normal" and self._command:
            try:
                self._command()
            except Exception:  # noqa: BLE001 — a bad callback must not crash the loop
                pass

    # API -----------------------------------------------------------------
    def set_text(self, text: str) -> None:
        self._text = text
        try:
            self._label.configure(text=text)
        except tk.TclError:
            pass

    def configure_state(self, state: str) -> None:
        self._state = state
        try:
            self.canvas.configure(cursor="hand2" if state == "normal" else "arrow")
        except tk.TclError:
            pass
        self._apply_state_colors()

    def set_kind(self, kind: str) -> None:
        self._kind = kind
        self._apply_state_colors()


# ── Switch ────────────────────────────────────────────────────────────────
class Switch(tk.Frame):
    """Animated on/off toggle bound to a ``BooleanVar``."""

    def __init__(self, parent, variable: Optional[tk.BooleanVar] = None,
                 command: Optional[Callable] = None, width: int = 46, height: int = 26):
        super().__init__(parent, bg=_bg_of(parent), highlightthickness=0)
        self.var = variable or tk.BooleanVar(value=False)
        self._cmd = command
        self._sw, self._sh = width, height
        self._pos = 1.0 if self.var.get() else 0.0

        self.canvas = tk.Canvas(self, width=width, height=height,
                                highlightthickness=0, bd=0, bg=_bg_of(parent),
                                cursor="hand2")
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._toggle)
        self.canvas.bind("<Configure>", lambda _e: self._draw())
        self._draw()

    def _draw(self) -> None:
        c = self.canvas
        c.delete("all")
        w, h = self._sw, self._sh
        on = self._pos
        track = theme.lerp_color(theme.TRACK, theme.ACCENT, on)
        rounded_rect(c, 0, 0, w - 1, h - 1, h // 2, fill=track, outline="")
        knob_r = h // 2 - 3
        cx = knob_r + 3 + (w - 2 * (knob_r + 3)) * on
        c.create_oval(cx - knob_r, h / 2 - knob_r, cx + knob_r, h / 2 + knob_r,
                      fill="#ffffff", outline="")

    def _toggle(self, _e=None) -> None:
        self.var.set(not self.var.get())
        target = 1.0 if self.var.get() else 0.0

        def tick() -> bool:
            step = theme.FPS_MS / theme.ANIM_SLIDE
            if self._pos < target:
                self._pos = min(target, self._pos + step)
            else:
                self._pos = max(target, self._pos - step)
            self._draw()
            return abs(self._pos - target) > 1e-3

        _Loop(self, tick).start()
        if self._cmd:
            try:
                self._cmd()
            except Exception:  # noqa: BLE001
                pass

    def set(self, value: bool) -> None:
        self.var.set(bool(value))
        self._pos = 1.0 if value else 0.0
        self._draw()

    def get(self) -> bool:
        return bool(self.var.get())


# ── SegmentedControl ──────────────────────────────────────────────────────
class SegmentedControl(tk.Frame):
    """Radio group with a sliding indicator; value in a ``StringVar``."""

    def __init__(self, parent, options: Sequence[tuple], variable: Optional[tk.StringVar] = None,
                 command: Optional[Callable] = None, values: Optional[Sequence[str]] = None):
        """``options`` = [(label, value), …]; ``values`` kept for clarity."""
        super().__init__(parent, bg=theme.SURFACE, highlightthickness=1,
                         highlightbackground=theme.BORDER, bd=0)
        self._segments = list(options)
        self.var = variable or tk.StringVar(value=self._segments[0][1] if self._segments else "")
        self._cmd = command
        self._labels: List[tk.Label] = []

        self._indicator = tk.Canvas(self, highlightthickness=0, bd=0,
                                    bg=theme.SURFACE_HI)
        # Lower the indicator window *behind* the segment labels (the Canvas
        # .lower() helper clashes with the canvas item-lowering command, so we
        # issue the window-level "lower" directly).
        self._indicator.tk.call("lower", self._indicator._w)
        for i, (label, value) in enumerate(self._segments):
            lbl = tk.Label(self, text=label, bg=theme.SURFACE, fg=theme.TEXT_DIM,
                           font=theme.FONT_SMALL, padx=12, pady=6, cursor="hand2")
            lbl.bind("<Button-1>", lambda _e, v=value: self.set(v))
            lbl.grid(row=0, column=i, sticky="nsew")
            self.columnconfigure(i, weight=1)
            self._labels.append(lbl)
        self.bind("<Configure>", lambda _e: self._place_indicator(instant=True))
        self.after(30, lambda: self._place_indicator(instant=True))
        self._sync_labels()

    def _index_of(self, value: str) -> int:
        for i, (_l, v) in enumerate(self._segments):
            if v == value:
                return i
        return 0

    def _sync_labels(self) -> None:
        cur = self.var.get()
        for i, (_l, v) in enumerate(self._segments):
            active = v == cur
            try:
                self._labels[i].configure(fg=theme.TEXT if active else theme.TEXT_DIM,
                                          font=(theme.FONT_SMALL[0], theme.FONT_SMALL[1],
                                                "bold" if active else "normal"))
            except tk.TclError:
                pass

    def _place_indicator(self, instant: bool = False) -> None:
        if not self._labels:
            return
        idx = self._index_of(self.var.get())
        target = self._labels[idx]
        try:
            x1 = target.winfo_x()
            x2 = x1 + target.winfo_width()
            y1, y2 = 2, target.winfo_height() - 2
        except tk.TclError:
            return
        self._sync_labels()

        if instant or not self._indicator.winfo_ismapped():
            self._draw_indicator(x1, x2, y1, y2)   # _draw_indicator lowers it
            return

        start = self._indicator.coords("ind")
        sx1 = start[0] if start else x1
        sx2 = start[2] if start else x2

        def tick() -> bool:
            cur = self._indicator.coords("ind")
            if not cur:
                self._draw_indicator(x1, x2, y1, y2)
                return False
            step = (x2 - x1) * (theme.FPS_MS / theme.ANIM_SLIDE)
            cx1, cx2 = cur[0], cur[2]
            if abs(cx1 - x1) < 0.5 and abs(cx2 - x2) < 0.5:
                self._draw_indicator(x1, x2, y1, y2)
                return False
            cx1 += step if x1 > cx1 else -step if x1 < cx1 else 0
            cx2 += step if x2 > cx2 else -step if x2 < cx2 else 0
            self._draw_indicator(cx1, cx2, y1, y2)
            return True

        _Loop(self, tick).start()

    def _draw_indicator(self, x1, x2, y1, y2) -> None:
        c = self._indicator
        c.place(x=0, y=0, relwidth=1, relheight=1)
        c.delete("all")
        rounded_rect(c, x1, y1, x2, y2, theme.RADIUS_SM - 2,
                     fill=theme.SURFACE_HI, outline=theme.BORDER_HI)
        c.tk.call("lower", c._w)

    def set(self, value: str) -> None:
        self.var.set(value)
        self._place_indicator()
        if self._cmd:
            try:
                self._cmd(value)
            except Exception:  # noqa: BLE001
                pass

    def set_labels(self, labels: Sequence[str]) -> None:
        """Relabel the segments in place (used by the language toggle)."""
        for lbl, text in zip(self._labels, labels):
            try:
                lbl.configure(text=text)
            except tk.TclError:
                pass

    def get(self) -> str:
        return self.var.get()


# ── AnimatedProgress ──────────────────────────────────────────────────────
class AnimatedProgress(tk.Frame):
    """Smooth indigo progress bar with an optional sweeping shimmer."""

    def __init__(self, parent, height: int = 16, shimmer: bool = True):
        super().__init__(parent, bg=_bg_of(parent), highlightthickness=0)
        self._target = 0.0
        self._value = 0.0
        self._shimmer_on = shimmer
        self._shimmer_x = -30.0
        self._active = False

        self.canvas = tk.Canvas(self, height=height, highlightthickness=0, bd=0,
                                bg=_bg_of(parent))
        self.canvas.pack(fill="x")
        self.canvas.bind("<Configure>", lambda _e: self._draw())
        self._loop = _Loop(self, self._tick)
        self._loop.start()

    def set(self, value: float, active: Optional[bool] = None) -> None:
        self._target = max(0.0, min(100.0, float(value)))
        if active is not None:
            self._active = active
        if not self._active and self._shimmer_on:
            # idle → stop the shimmer sweep (saves frames)
            self._shimmer_x = -30.0

    def reset(self) -> None:
        self._target = 0.0
        self._value = 0.0
        self._active = False

    def _tick(self) -> bool:
        moved = False
        step = theme.FPS_MS / theme.ANIM_PROGRESS
        if abs(self._target - self._value) > 0.05:
            if self._value < self._target:
                self._value = min(self._target, self._value + max(0.6, (self._target - self._value) * step))
            else:
                self._value = max(self._target, self._value - step)
            moved = True
        if self._shimmer_on and self._active:
            self._shimmer_x += 2.2
            w = max(1, self.canvas.winfo_width())
            if self._shimmer_x > w + 30:
                self._shimmer_x = -30.0
            moved = True
        if moved:
            self._draw()
        return True  # keep ticking (cheap) so transitions stay smooth

    def _draw(self) -> None:
        c = self.canvas
        try:
            w = max(1, c.winfo_width())
        except tk.TclError:
            return
        h = int(c.cget("height"))
        c.delete("all")
        rounded_rect(c, 0, 0, w - 1, h - 1, h // 2, fill=theme.TRACK, outline="")
        fill_w = int(w * self._value / 100.0)
        if fill_w > h:
            # gradient-ish: draw base fill then a lighter cap
            rounded_rect(c, 0, 0, fill_w, h - 1, h // 2, fill=theme.ACCENT, outline="")
            cap_w = max(h, int(fill_w * 0.5))
            rounded_rect(c, 0, 0, cap_w, h - 1, h // 2, fill=theme.ACCENT_2, outline="")
            rounded_rect(c, 0, 0, fill_w, h - 1, h // 2, fill="", outline="")
        elif fill_w > 1:
            rounded_rect(c, 0, 0, fill_w, h - 1, fill_w // 2, fill=theme.ACCENT, outline="")
        # shimmer sweep (clipped to the filled region)
        if self._shimmer_on and self._active and fill_w > 8:
            sx = self._shimmer_x
            band = 26
            x1 = max(0, sx)
            x2 = min(fill_w, sx + band)
            if x2 > x1:
                c.create_rectangle(x1, 2, x2, h - 2, fill=theme.SHIMMER, outline="",
                                   stipple="gray50")


# ── Badge ─────────────────────────────────────────────────────────────────
class Badge(tk.Frame):
    """Small pill chip for statuses."""

    def __init__(self, parent, text: str = "", tone: str = "neutral"):
        super().__init__(parent, bg=_bg_of(parent), highlightthickness=0)
        self._tones = {
            "neutral": (theme.SURFACE_HI, theme.TEXT_DIM),
            "accent": (theme.ACCENT_DEEP, "#ffffff"),
            "success": (theme.SUCCESS_DIM, "#bbf7d0"),
            "warn": ("#78350f", "#fde68a"),
            "danger": (theme.DANGER_DEEP, "#fecaca"),
        }
        self._lbl = tk.Label(self, text=text, padx=8, pady=2,
                             font=theme.FONT_TINY, **self._style(tone))
        self._lbl.pack()

    def _style(self, tone):
        bg, fg = self._tones.get(tone, self._tones["neutral"])
        return {"bg": bg, "fg": fg}

    def set(self, text: str, tone: str = "neutral") -> None:
        try:
            self._lbl.configure(text=text, **self._style(tone))
        except tk.TclError:
            pass
