"""M8 macro — the rebuilt, modern, bilingual desktop UI.

What changed vs the old Tkinter app (and why it no longer “hangs”):

* **Never blocks**: every click just queues work; a ``root.after(60ms)``
  ticker drains the :class:`app.processor.Processor` event queue and paints.
  There is no ``update()``-spinning and no cross-thread widget access.
* **Modern look**: rounded cards, animated buttons/switches/progress,
  a stage “stepper”, and a soft color palette from :mod:`app.theme`.
* **Bilingual**: a live **عربي / EN** toggle re-labels every widget and
  mirrors the layout (RTL/LTR) through :mod:`app.i18n`.
* **Path-ordered batches**: pick files *or* a whole folder; the list is
  processed in natural path order, reorderable with ▲▼.
* **Full options**: Whisper model · local/Google/no-translation · SRT/VTT/both
  · save next to the video (default) · promo credit · optional burn-in · BOM.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path

from app import __app_name__, __version__
from app import i18n, theme
from app.processor import Processor, default_options
from app.reshape import shaped
from app.widgets import (
    AnimatedProgress,
    Badge,
    Card,
    ModernButton,
    SegmentedControl,
    Switch,
    rounded_rect,
)
from core import batch as batch_mod
from core import credit as credit_mod
from core.models import MODEL_SIZES
from core.pipeline import burn_status

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pystray
    from pystray import MenuItem as TrayItem
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

GITHUB_URL = "https://github.com/RaGAEIDOS/video2arabicsubs"

#: Stepper stages shown while a job runs.
_STEPPER = ["extracting", "transcribing", "translating", "generating", "burning"]

_MODEL_LABELS = {
    "ar": {"tiny": "tiny", "base": "base", "small": "small",
           "medium": "medium", "large": "large", "turbo": "turbo"},
    "en": {"tiny": "tiny", "base": "base", "small": "small",
           "medium": "medium", "large": "large", "turbo": "turbo"},
}

_MODEL_HINTS = {
    "ar": {"tiny": "الأسرع · دقة أقل", "base": "سريع", "small": "موصى به",
           "medium": "أدق · أبطأ", "large": "الأدق · ثقيل", "turbo": "سريع ودقيق"},
    "en": {"tiny": "Fastest · less accurate", "base": "Fast", "small": "Recommended",
           "medium": "More accurate", "large": "Most accurate · heavy", "turbo": "Fast + accurate"},
}


class App:
    def __init__(self, lang: str = None):
        self.lang = lang or i18n.DEFAULT_LANG
        self.rtl = i18n.is_rtl(self.lang)

        self.videos: list[str] = []
        self.status: dict[str, str] = {}     # path → pending/active/done/error/cancelled
        self.selected: int | None = None

        self.processor = Processor()
        self._burn = burn_status()
        self._closing = False
        self._ticker = None

        # The root window must exist before any Tk variable is created.
        self._build_root()

        # Tk vars
        self.var_model = tk.StringVar(value="small")
        self.var_engine = tk.StringVar(value="argos")
        self.var_format = tk.StringVar(value="both")
        self.var_where = tk.StringVar(value="next")
        self.var_custom = tk.StringVar(value=str(Path.home() / "Videos" / "subtitles"))
        self.var_credit = tk.BooleanVar(value=True)
        self.var_burn = tk.BooleanVar(value=False)
        self.var_bom = tk.BooleanVar(value=False)
        self.var_recursive = tk.BooleanVar(value=False)

        self._build_header()
        self._build_body()
        self._setup_tray()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._apply_language()
        self._start_ticker()

    # ── window ─────────────────────────────────────────────
    def _build_root(self):
        self.root = tk.Tk()
        self.root.title(f"{__app_name__} v{__version__}")
        self.root.geometry("1040x760")
        self.root.minsize(900, 640)
        self.root.configure(bg=theme.BG)

        # Center on screen
        self.root.update_idletasks()
        w, h = 1040, 760
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    # ── header ─────────────────────────────────────────────
    def _build_header(self):
        self.header = tk.Frame(self.root, bg=theme.BG, highlightthickness=1,
                               highlightbackground=theme.BORDER)
        self.header.pack(fill="x", side="top")

        # gradient strip
        strip = tk.Canvas(self.header, height=3, highlightthickness=0, bd=0, bg=theme.BG)
        strip.pack(fill="x")
        self._paint_gradient(strip)

        inner = tk.Frame(self.header, bg=theme.BG)
        inner.pack(fill="x", padx=18, pady=12)

        self.logo_img = None
        logo_path = Path(__file__).resolve().parent.parent / "img" / "first-logo-design.png"
        if logo_path.exists() and HAS_PIL:
            try:
                img = Image.open(logo_path).convert("RGBA").resize((52, 52), Image.LANCZOS)
                # Round the corners a touch via a mask
                self.logo_img = ImageTk.PhotoImage(img)
                tk.Label(inner, image=self.logo_img, bg=theme.BG).pack(
                    side="left", padx=(0, 12))
            except Exception:  # noqa: BLE001
                pass

        text_col = tk.Frame(inner, bg=theme.BG)
        text_col.pack(side="left", fill="x", expand=True)

        self.lbl_title = tk.Label(text_col, text=__app_name__, bg=theme.BG,
                                  fg=theme.TEXT, font=("Segoe UI", 22, "bold"))
        self.lbl_title.pack(anchor="w")
        self.lbl_tag = tk.Label(text_col, text="", bg=theme.BG, fg=theme.TEXT_DIM,
                                font=theme.FONT_SMALL)
        self.lbl_tag.pack(anchor="w")

        # right side controls
        ctrl = tk.Frame(inner, bg=theme.BG)
        ctrl.pack(side="right")

        self.btn_github = ModernButton(ctrl, text="GitHub  ★", kind="ghost",
                                       command=self._open_github)
        self.btn_github.pack(side="left", padx=(0, 8))

        self.lang_switch = SegmentedControl(
            ctrl, options=[("EN", "en"), ("عربي", "ar")],
            variable=tk.StringVar(value=self.lang), command=self._set_lang,
        )
        self.lang_switch.pack(side="left")

    def _paint_gradient(self, canvas):
        w = max(canvas.winfo_width(), 1040)
        canvas.delete("g")
        steps = 48
        for i in range(steps):
            color = theme.lerp_color(theme.ACCENT, theme.ACCENT_2, i / (steps - 1))
            x1 = int(w * i / steps)
            x2 = int(w * (i + 1) / steps) + 1
            canvas.create_rectangle(x1, 0, x2, 3, fill=color, outline="", tags="g")
        canvas.bind("<Configure>", lambda e: self._paint_gradient(canvas))

    # ── body ───────────────────────────────────────────────
    def _build_body(self):
        self.body = tk.Frame(self.root, bg=theme.BG)
        self.body.pack(fill="both", expand=True, padx=18, pady=14)

        # two columns; order flipped for RTL
        self.col_left = tk.Frame(self.body, bg=theme.BG)
        self.col_right = tk.Frame(self.body, bg=theme.BG)

        self._build_source_card(self.col_left)
        self._build_options_card(self.col_left)
        self._build_job_card(self.col_right)

        self._pack_columns()

    def _pack_columns(self):
        for col in (self.col_left, self.col_right):
            col.pack_forget()
        if self.rtl:
            self.col_right.pack(side="left", fill="both", expand=True, padx=(0, 7))
            self.col_left.pack(side="left", fill="both", expand=True, padx=(7, 0))
        else:
            self.col_left.pack(side="left", fill="both", expand=True, padx=(0, 7))
            self.col_right.pack(side="left", fill="both", expand=True, padx=(7, 0))
        self.col_left.pack_propagate(False)
        self.col_right.pack_propagate(False)
        # left column holds source+options; give it a bit less width
        self.col_left.configure(width=470)
        self.col_right.configure(width=520)

    # ── source card ────────────────────────────────────────
    def _build_source_card(self, parent):
        self.card_source = Card(parent, title="", accent=True)
        self.card_source.pack(fill="both", expand=True, pady=(0, theme.GAP))

        b = self.card_source.body

        # tab row: files / folder
        tab_row = tk.Frame(b, bg=theme.SURFACE)
        tab_row.pack(fill="x", pady=(0, 8))
        self.btn_files = ModernButton(tab_row, text="", kind="primary",
                                      command=self._pick_files)
        self.btn_files.pack(side="left", padx=(0, 6))
        self.btn_folder = ModernButton(tab_row, text="", kind="ghost",
                                       command=self._pick_folder)
        self.btn_folder.pack(side="left")

        self.chk_recursive = Switch(tab_row, variable=self.var_recursive)
        self.lbl_recursive = tk.Label(tab_row, text="", bg=theme.SURFACE,
                                      fg=theme.TEXT_DIM, font=theme.FONT_TINY)

        # list area (canvas + rows)
        list_wrap = tk.Frame(b, bg=theme.SURFACE)
        list_wrap.pack(fill="both", expand=True)
        self.list_canvas = tk.Canvas(list_wrap, bg=theme.SURFACE, highlightthickness=0,
                                     bd=0)
        scrollbar = tk.Scrollbar(list_wrap, orient="vertical",
                                 command=self.list_canvas.yview)
        self.rows_frame = tk.Frame(self.list_canvas, bg=theme.SURFACE)
        self.rows_frame.bind("<Configure>", lambda e: self.list_canvas.configure(
            scrollregion=self.list_canvas.bbox("all")))
        self._rows_win = self.list_canvas.create_window((0, 0), window=self.rows_frame,
                                                        anchor="nw")
        self.list_canvas.configure(yscrollcommand=scrollbar.set)
        self.list_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.list_canvas.bind("<Configure>", self._on_list_configure)

        # footer: count + reorder/remove/clear
        foot = tk.Frame(b, bg=theme.SURFACE)
        foot.pack(fill="x", pady=(8, 0))
        self.lbl_count = tk.Label(foot, text="", bg=theme.SURFACE, fg=theme.TEXT_FAINT,
                                  font=theme.FONT_TINY)
        self.lbl_count.pack(side="left")

        btn_col = tk.Frame(foot, bg=theme.SURFACE)
        btn_col.pack(side="right")
        self.btn_up = ModernButton(btn_col, text="▲", kind="ghost", pad_x=8,
                                   command=lambda: self._move(-1))
        self.btn_down = ModernButton(btn_col, text="▼", kind="ghost", pad_x=8,
                                     command=lambda: self._move(1))
        self.btn_del = ModernButton(btn_col, text="✕", kind="danger", pad_x=8,
                                    command=self._remove)
        self.btn_up.pack(side="left", padx=2)
        self.btn_down.pack(side="left", padx=2)
        self.btn_del.pack(side="left", padx=2)

        self._render_rows()

    def _on_list_configure(self, _e=None):
        self.list_canvas.itemconfigure(self._rows_win,
                                       width=self.list_canvas.winfo_width())

    # ── options card ───────────────────────────────────────
    def _build_options_card(self, parent):
        self.card_options = Card(parent, title="")
        self.card_options.pack(fill="both", expand=False)
        b = self.card_options.body

        # model
        self.lbl_model = self._field_label(b, "opt.model")
        model_opts = [(m, m) for m in MODEL_SIZES]
        self.seg_model = SegmentedControl(b, options=model_opts, variable=self.var_model)
        self.seg_model.pack(fill="x", pady=(2, 2))
        self.lbl_model_hint = tk.Label(b, text="", bg=theme.SURFACE, fg=theme.TEXT_FAINT,
                                       font=theme.FONT_TINY, anchor="w")
        self.lbl_model_hint.pack(fill="x")

        # engine
        self.lbl_engine = self._field_label(b, "opt.engine")
        self.seg_engine = SegmentedControl(
            b,
            options=[("local", "argos"), ("google", "google"), ("none", "none")],
            variable=self.var_engine, command=self._on_engine,
        )
        self.seg_engine.pack(fill="x", pady=(2, 8))

        # format
        self.lbl_format = self._field_label(b, "opt.format")
        self.seg_format = SegmentedControl(
            b, options=[("SRT", "srt"), ("VTT", "vtt"), ("SRT+VTT", "both")],
            variable=self.var_format,
        )
        self.seg_format.pack(fill="x", pady=(2, 8))

        # where to save
        self.lbl_where = self._field_label(b, "opt.where")
        self.seg_where = SegmentedControl(
            b, options=[("next", "next"), ("custom", "custom")],
            variable=self.var_where, command=self._on_where,
        )
        self.seg_where.pack(fill="x", pady=(2, 4))

        custom_row = tk.Frame(b, bg=theme.SURFACE)
        custom_row.pack(fill="x")
        self.entry_custom = tk.Entry(custom_row, textvariable=self.var_custom,
                                     bg=theme.SURFACE_HI, fg=theme.TEXT,
                                     insertbackground=theme.TEXT,
                                     relief="flat", font=theme.FONT_SMALL,
                                     highlightthickness=1,
                                     highlightbackground=theme.BORDER)
        self.entry_custom.pack(side="left", fill="x", expand=True, ipady=5)
        self.btn_browse = ModernButton(custom_row, text="", kind="ghost",
                                       command=self._browse_custom)
        self.btn_browse.pack(side="right", padx=(6, 0))
        self.btn_browse.pack_forget()
        self.custom_row_shown = False
        self._on_where(self.var_where.get())   # hide custom row initially

        # toggles
        sep = tk.Frame(b, bg=theme.BORDER, height=1)
        sep.pack(fill="x", pady=10)
        self.lbl_extras = self._field_label(b, "opt.toggles", pady=(0, 6))

        self.row_credit = self._toggle_row(
            b, self.var_credit, "opt.credit", hint=credit_mod.CREDIT_TEXT)
        self.row_burn = self._toggle_row(b, self.var_burn, "opt.burn")
        self.row_bom = self._toggle_row(b, self.var_bom, "opt.bom")

        if not self._burn.get("available", False):
            self.var_burn.set(False)
            self.btn_burn_widget.configure_state("disabled")

    def _field_label(self, parent, key, pady=(10, 2)):
        lbl = tk.Label(parent, text="", bg=theme.SURFACE, fg=theme.TEXT_DIM,
                       font=theme.FONT_SMALL, anchor="w")
        lbl.pack(fill="x", pady=pady)
        setattr(self, f"_key_{id(lbl)}", key)
        # register for language refresh
        if not hasattr(self, "_translatable"):
            self._translatable = []
        self._translatable.append((lbl, key, {}))
        return lbl

    def _toggle_row(self, parent, var, key, hint=None):
        row = tk.Frame(parent, bg=theme.SURFACE)
        row.pack(fill="x", pady=3)
        sw = Switch(row, variable=var)
        sw.pack(side="left")
        text_col = tk.Frame(row, bg=theme.SURFACE)
        text_col.pack(side="left", fill="x", expand=True, padx=(8, 0))
        lbl = tk.Label(text_col, text="", bg=theme.SURFACE, fg=theme.TEXT,
                       font=theme.FONT_SMALL, anchor="w")
        lbl.pack(anchor="w")
        if not hasattr(self, "_translatable"):
            self._translatable = []
        self._translatable.append((lbl, key, {}))
        if hint:
            hl = tk.Label(text_col, text="", bg=theme.SURFACE, fg=theme.TEXT_FAINT,
                          font=theme.FONT_TINY, anchor="w")
            hl.pack(anchor="w")
            self._translatable.append((hl, "opt.credit_hint", {"text": hint}))
        if key == "opt.burn":
            self.btn_burn_widget = sw
            self._burn_hint_lbl = tk.Label(text_col, text="", bg=theme.SURFACE,
                                           fg=theme.WARN, font=theme.FONT_TINY,
                                           anchor="w")
            if not self._burn.get("available", False):
                self._burn_hint_lbl.pack(anchor="w")
        return row

    # ── job card ───────────────────────────────────────────
    def _build_job_card(self, parent):
        self.card_job = Card(parent, title="")
        self.card_job.pack(fill="both", expand=True)
        b = self.card_job.body

        # stepper
        self.stepper = tk.Frame(b, bg=theme.SURFACE)
        self.stepper.pack(fill="x", pady=(2, 12))
        self._step_chips = {}
        for key in _STEPPER:
            chip = self._make_chip(self.stepper, key)
            self._step_chips[key] = chip

        # current file + percent
        info = tk.Frame(b, bg=theme.SURFACE)
        info.pack(fill="x")
        self.lbl_current = tk.Label(info, text="", bg=theme.SURFACE, fg=theme.TEXT_DIM,
                                    font=theme.FONT_SMALL, anchor="w")
        self.lbl_current.pack(side="left")
        self.lbl_percent = tk.Label(info, text="0%", bg=theme.SURFACE, fg=theme.ACCENT_HI,
                                    font=("Consolas", 14, "bold"))
        self.lbl_percent.pack(side="right")

        # progress
        self.progress = AnimatedProgress(b, height=18)
        self.progress.pack(fill="x", pady=(6, 12))

        # buttons
        btn_row = tk.Frame(b, bg=theme.SURFACE)
        btn_row.pack(fill="x", pady=(0, 10))
        self.btn_start = ModernButton(btn_row, text="", kind="primary",
                                      command=self._start)
        self.btn_start.pack(side="left", padx=(0, 6))
        self.btn_stop = ModernButton(btn_row, text="", kind="danger",
                                     command=self._stop, state="disabled")
        self.btn_stop.pack(side="left")

        # log
        log_head = tk.Frame(b, bg=theme.SURFACE)
        log_head.pack(fill="x")
        self.lbl_log_title = tk.Label(log_head, text="", bg=theme.SURFACE,
                                      fg=theme.TEXT_DIM, font=theme.FONT_SMALL)
        self.lbl_log_title.pack(side="left")
        self.btn_log_clear = tk.Label(log_head, text="", bg=theme.SURFACE,
                                      fg=theme.TEXT_FAINT, font=theme.FONT_TINY,
                                      cursor="hand2")
        self.btn_log_clear.pack(side="right")
        self.btn_log_clear.bind("<Button-1>", lambda e: self._clear_log())

        self.log = tk.Text(b, height=12, wrap="word", bg="#0a0f1c", fg=theme.TEXT_DIM,
                           insertbackground=theme.TEXT, relief="flat",
                           font=("Consolas", 9), state="disabled",
                           highlightthickness=1, highlightbackground=theme.BORDER)
        self.log.pack(fill="both", expand=True, pady=(4, 0), ipady=4)
        self.log.tag_configure("err", foreground=theme.DANGER)
        self.log.tag_configure("ok", foreground=theme.SUCCESS)
        self.log.tag_configure("info", foreground=theme.ACCENT_HI)

        self._reset_stepper()

    def _make_chip(self, parent, key):
        chip = tk.Frame(parent, bg=theme.SURFACE_HI, highlightthickness=1,
                        highlightbackground=theme.BORDER)
        dot = tk.Canvas(chip, width=10, height=10, bg=theme.SURFACE_HI,
                        highlightthickness=0, bd=0)
        dot_id = dot.create_oval(2, 2, 8, 8, fill=theme.TEXT_FAINT, outline="")
        lbl = tk.Label(chip, text="", bg=theme.SURFACE_HI, fg=theme.TEXT_FAINT,
                       font=theme.FONT_TINY)
        dot.pack(side="left", padx=(8, 4), pady=5)
        lbl.pack(side="left", padx=(0, 8), pady=5)
        chip.pack(side="left", padx=(0, 5))
        return {"frame": chip, "dot": dot, "dot_id": dot_id, "label": lbl, "key": key}

    def _reset_stepper(self):
        for key, chip in self._step_chips.items():
            self._style_chip(chip, "pending")

    def _style_chip(self, chip, state):
        chip["state"] = state  # remembered so a language switch can re-paint it
        if state == "active":
            bg, border, fg, dot = theme.ACCENT_DEEP, theme.ACCENT, "#ffffff", theme.ACCENT_HI
        elif state == "done":
            bg, border, fg, dot = theme.SURFACE_HI, theme.SUCCESS, theme.TEXT, theme.SUCCESS
        elif state == "error":
            bg, border, fg, dot = theme.SURFACE_HI, theme.DANGER, theme.TEXT, theme.DANGER
        else:  # pending
            bg, border, fg, dot = theme.SURFACE_HI, theme.BORDER, theme.TEXT_FAINT, theme.TEXT_FAINT
        try:
            chip["frame"].configure(bg=bg, highlightbackground=border)
            chip["dot"].configure(bg=bg)
            chip["dot"].itemconfigure(chip["dot_id"], fill=dot)
            chip["label"].configure(text=shaped(i18n.tr(self.lang, f"stage.{chip['key']}")),
                                    bg=bg, fg=fg)
        except tk.TclError:
            pass

    def _update_stepper(self, stage):
        """Mark chips done/active based on the current pipeline stage."""
        try:
            order = [k for k in _STEPPER]
            if hasattr(stage, "value"):
                stage = stage.value
            if stage in ("done",):
                for key in order:
                    self._style_chip(self._step_chips[key], "done")
                return
            if stage in ("error", "cancelled"):
                for key in order:
                    self._style_chip(self._step_chips[key],
                                     "error" if stage == "error" else "pending")
                return
            if stage not in order:
                return
            cur = order.index(stage)
            for i, key in enumerate(order):
                if i < cur:
                    self._style_chip(self._step_chips[key], "done")
                elif i == cur:
                    self._style_chip(self._step_chips[key], "active")
                else:
                    self._style_chip(self._step_chips[key], "pending")
        except Exception:  # noqa: BLE001
            pass

    # ── language ───────────────────────────────────────────
    def _set_lang(self, value):
        self.lang = value
        self.rtl = i18n.is_rtl(value)
        self._apply_language()
        self._pack_columns()
        self._render_rows()
        # Re-paint the stepper chips in the new language while keeping each
        # chip's current state (the state lives on the chip itself — deriving
        # it from _last_stage fails before the first progress event).
        for chip in getattr(self, "_step_chips", {}).values():
            self._style_chip(chip, chip.get("state", "pending"))
        # …and the live status line, from its logical key + kwargs.
        if getattr(self, "_status_key", None):
            self._set_status(self._status_key, **getattr(self, "_status_kw", {}))

    def _t(self, key, **kw):
        return i18n.tr(self.lang, key, **kw)

    def _set_status(self, key, **kw):
        """Update the live status label from an i18n key (logical → shaped).

        The key/kwargs are remembered so switching languages re-renders the
        line in the new language instead of leaving the old text behind.
        """
        self._status_key, self._status_kw = key, kw
        self.lbl_current.configure(text=shaped(self._t(key, **kw)))

    def _apply_language(self):
        # NOTE: `tr` here feeds *raw* tk labels, so each result goes through
        # shaped(). The widget setters (Card.set_title / ModernButton.set_text /
        # SegmentedControl.set_labels) already shape internally — never shape
        # their arguments too (shaping is single-pass, not idempotent).
        tr = self._t
        self.root.title(f"{__app_name__} v{__version__}")
        self.lbl_title.configure(text=__app_name__)
        self.lbl_tag.configure(text=shaped(tr("app.tagline")))

        # source card
        self.card_source.set_title(tr("source.title"), "🎬")
        self.btn_files.set_text(tr("source.files"))
        self.btn_folder.set_text(tr("source.folder"))
        self.lbl_recursive.configure(text=shaped(tr("source.recursive")))
        self.lbl_log_title.configure(text=shaped(tr("job.log")))
        self.btn_log_clear.configure(text=shaped(tr("job.log_clear")))

        # options card
        self.card_options.set_title(tr("opt.title"), "⚙️")
        self.lbl_engine.configure(text=shaped(tr("opt.engine")))
        self.seg_engine.set_labels([tr("opt.engine_local"), tr("opt.engine_google"),
                                    tr("opt.engine_none")])
        self.lbl_format.configure(text=shaped(tr("opt.format")))
        self.seg_format.set_labels([tr("opt.fmt_srt"), tr("opt.fmt_vtt"), tr("opt.fmt_both")])
        self.lbl_where.configure(text=shaped(tr("opt.where")))
        self.seg_where.set_labels([tr("opt.next_to_video"), tr("opt.custom_folder")])
        self.btn_browse.set_text(tr("opt.custom_folder_btn"))
        self.lbl_extras.configure(text=shaped(tr("opt.toggles")))

        # job card
        self.card_job.set_title(tr("job.title"), "⏳")
        self.btn_start.set_text(tr("job.start"))
        self.btn_stop.set_text(tr("job.stop"))
        self._update_model_hint()
        self._update_burn_hint()
        self._refresh_translatable()

    def _refresh_translatable(self):
        for lbl, key, kw in getattr(self, "_translatable", []):
            try:
                lbl.configure(text=shaped(self._t(key, **kw)))
            except tk.TclError:
                pass

    def _update_model_hint(self):
        hints = _MODEL_HINTS.get(self.lang, _MODEL_HINTS["en"])
        self.lbl_model_hint.configure(text=shaped(hints.get(self.var_model.get(), "")))

    def _on_engine(self, value):
        pass

    def _update_burn_hint(self):
        if not hasattr(self, "_burn_hint_lbl"):
            return
        if self._burn.get("available", False):
            self._burn_hint_lbl.configure(text="")
        else:
            self._burn_hint_lbl.configure(
                text=shaped(self._burn.get("reason", "") or
                            self._t("opt.burn_unavailable")))

    # ── file picking ───────────────────────────────────────
    def _pick_files(self):
        from tkinter import filedialog
        exts = " ".join(f"*{e}" for e in batch_mod.VIDEO_EXTENSIONS)
        paths = filedialog.askopenfilenames(title=self._t("source.pick_files"),
                                            filetypes=[("Videos", exts)])
        added = 0
        for p in paths:
            if p not in self.videos:
                self.videos.append(p)
                self.status[p] = "pending"
                added += 1
        if added:
            self._render_rows()

    def _pick_folder(self):
        from tkinter import filedialog, messagebox
        folder = filedialog.askdirectory(title=self._t("source.pick_folder"))
        if not folder:
            return
        found = batch_mod.scan_video_files(folder, recursive=self.var_recursive.get())
        added = 0
        for p in found:
            if p not in self.videos:
                self.videos.append(p)
                self.status[p] = "pending"
                added += 1
        self._log(self._t("source.folder_loaded", n=len(found), path=folder), "info")
        self._render_rows()

    def _browse_custom(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory(title=self._t("opt.custom_folder"))
        if folder:
            self.var_custom.set(folder)

    def _on_where(self, value):
        # The custom-folder row is only relevant when selected.
        show = value == "custom"
        if show and not self.custom_row_shown:
            self.entry_custom.pack(side="left", fill="x", expand=True, ipady=5)
            self.btn_browse.pack(side="right", padx=(6, 0))
            self.custom_row_shown = True
        elif not show and self.custom_row_shown:
            self.entry_custom.pack_forget()
            self.btn_browse.pack_forget()
            self.custom_row_shown = False

    # ── list rendering ─────────────────────────────────────
    def _render_rows(self):
        for child in self.rows_frame.winfo_children():
            child.destroy()

        if not self.videos:
            empty = tk.Label(self.rows_frame, text=shaped(self._t("source.empty")),
                             bg=theme.SURFACE, fg=theme.TEXT_FAINT,
                             font=theme.FONT_SMALL, justify="center")
            empty.pack(pady=30, padx=10, fill="x")
            self._update_count()
            return

        for i, path in enumerate(self.videos):
            self._render_row(i, path)
        self._update_count()

    def _render_row(self, i, path):
        st = self.status.get(path, "pending")
        row_bg = theme.SURFACE_HI if self.selected == i else theme.SURFACE
        row = tk.Frame(self.rows_frame, bg=row_bg, highlightthickness=1,
                       highlightbackground=theme.BORDER)
        row.pack(fill="x", pady=2, padx=1)
        row.bind("<Button-1>", lambda e, idx=i: self._select(idx))
        for child in row.winfo_children():
            child.bind("<Button-1>", lambda e, idx=i: self._select(idx))

        # index badge
        idx_lbl = tk.Label(row, text=str(i + 1), width=3, bg=theme.ACCENT_DEEP,
                           fg="#ffffff", font=("Consolas", 9, "bold"))
        idx_lbl.pack(side="left", padx=(4, 8), pady=5)
        idx_lbl.bind("<Button-1>", lambda e, idx=i: self._select(idx))

        # name + path
        name_col = tk.Frame(row, bg=row_bg)
        name_col.pack(side="left", fill="x", expand=True)
        name = os.path.basename(path)
        tk.Label(name_col, text=shaped(name), bg=row_bg, fg=theme.TEXT, font=theme.FONT_SMALL,
                 anchor="w").pack(anchor="w")
        tk.Label(name_col, text=shaped(os.path.dirname(path)), bg=row_bg, fg=theme.TEXT_FAINT,
                 font=theme.FONT_TINY, anchor="w").pack(anchor="w")
        for child in name_col.winfo_children():
            child.bind("<Button-1>", lambda e, idx=i: self._select(idx))

        # status badge
        tone_map = {"pending": "neutral", "active": "accent", "done": "success",
                    "error": "danger", "cancelled": "warn"}
        badge = Badge(row, text=self._t(f"status.{st}"), tone=tone_map.get(st, "neutral"))
        badge.pack(side="right", padx=8)

    def _select(self, idx):
        self.selected = idx
        self._render_rows()

    def _update_count(self):
        self.lbl_count.configure(text=shaped(self._t("source.count", n=len(self.videos))))

    def _move(self, delta):
        if self.selected is None:
            return
        i = self.selected
        j = i + delta
        if 0 <= j < len(self.videos):
            self.videos[i], self.videos[j] = self.videos[j], self.videos[i]
            self.selected = j
            self._render_rows()

    def _remove(self):
        if self.selected is None:
            return
        i = self.selected
        path = self.videos.pop(i)
        self.status.pop(path, None)
        self.selected = None if i >= len(self.videos) else i
        self._render_rows()

    # ── logging / progress ─────────────────────────────────
    def _log(self, text, tag=None):
        # Every log line is shaped here, exactly once, before it enters the
        # Text widget (callers always pass logical text).
        text = shaped(text)
        self.log.configure(state="normal")
        if tag:
            self.log.insert("end", text + "\n", tag)
        else:
            self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    # ── processing control ─────────────────────────────────
    def _gather_options(self):
        engine = self.var_engine.get()
        # custom "where" only affects a copy destination; core writes next to
        # the video. We keep burn/credit/bom/format from the UI.
        return default_options(
            model_size=self.var_model.get(),
            engine=engine,
            output_format=self.var_format.get(),
            burn_video=self.var_burn.get() and self._burn.get("available", False),
            add_credit=self.var_credit.get(),
            add_bom=self.var_bom.get(),
        )

    def _start(self):
        if not self.videos:
            from tkinter import messagebox
            # the dialog *title* stays logical: the window manager (Pango)
            # shapes it natively — only the Tk-rendered message needs shaping.
            messagebox.showwarning(self._t("dlg.warn_title"),
                                   shaped(self._t("job.need_input")))
            return
        self._log_clear_safe()
        self.progress.reset()
        self.progress.set(0, active=True)
        self.lbl_percent.configure(text="0%")
        self._reset_stepper()
        self._last_stage = "queued"

        # refresh statuses
        for p in self.videos:
            self.status[p] = "pending"
        self._render_rows()

        opts = self._gather_options()
        order = "path" if self.var_where.get() else "path"
        ok = self.processor.start(list(self.videos), opts, order="given")
        if not ok:
            return
        self.btn_start.configure_state("disabled")
        self.btn_stop.configure_state("normal")
        self._set_status("job.running")

    def _log_clear_safe(self):
        self._clear_log()

    def _stop(self):
        self.processor.cancel()
        self.btn_stop.configure_state("disabled")
        self._log(self._t("job.cancelled"), "err")

    # ── ticker (drains the processor queue — never blocks) ──
    def _start_ticker(self):
        def tick():
            if self._closing:
                return
            try:
                self._drain_events()
            except Exception:  # noqa: BLE001 — a paint error must not kill the loop
                pass
            self._ticker = self.root.after(60, tick)
        self._ticker = self.root.after(60, tick)

    def _drain_events(self):
        for ev in self.processor.drain():
            t = ev.get("type")
            if t == "progress":
                self._on_progress_event(ev)
            elif t == "item":
                self._on_item_event(ev)
            elif t == "batch_start":
                self._set_status("job.progress_of", i=0, n=ev.get("total", 0))
            elif t == "batch_end":
                self._on_batch_end(ev)
            elif t == "fatal":
                self._log(f"✕ {ev.get('error')}", "err")

    def _on_progress_event(self, ev):
        pct = ev.get("percent", 0.0)
        self.progress.set(pct, active=True)
        self.lbl_percent.configure(text=f"{pct:.0f}%")
        stage = ev.get("stage")
        self._last_stage = getattr(stage, "value", stage)
        self._update_stepper(stage)

    def _on_item_event(self, ev):
        e = ev.get("event")
        if e is None:
            return
        kind_map = {"item_start": "active", "item_done": "done",
                    "item_error": "error", "item_cancelled": "cancelled"}
        st = kind_map.get(e.kind)
        if st:
            self.status[e.path] = st
            self._render_rows()
        if e.kind == "item_start":
            self._set_status("job.current", name=e.name)
            self._log(f"▶ [{e.index + 1}/{e.total}] {e.name}", "info")
        elif e.kind == "item_done":
            files = ", ".join(os.path.basename(p) for p in e.files.values())
            self._log(f"✔ {e.name} — {self._t('job.cues', n=e.cues)} · {files}", "ok")
        elif e.kind == "item_error":
            self._log(f"✘ {e.name}: {e.error}", "err")

    def _on_batch_end(self, ev):
        self.progress.set(100 if not ev.get("cancelled") else self._last_percent(), active=False)
        self.btn_start.configure_state("normal")
        self.btn_stop.configure_state("disabled")
        done, failed, cancelled = ev.get("done", []), ev.get("failed", []), ev.get("cancelled")
        if cancelled:
            self._log(self._t("job.cancelled"), "err")
            self._set_status("job.cancelled")
        else:
            summary = self._t("job.done_sub", ok=len(done), total=ev.get("total", 0))
            self._log(self._t("job.done"), "ok")
            self._log(summary, "ok")
            self._set_status("job.done_sub", ok=len(done), total=ev.get("total", 0))
            self._update_stepper("done")

    def _last_percent(self):
        try:
            return float(self.lbl_percent.cget("text").rstrip("%") or 0)
        except Exception:  # noqa: BLE001
            return 0.0

    # ── tray / close ───────────────────────────────────────
    def _setup_tray(self):
        if not HAS_TRAY:
            return
        try:
            img_path = Path(__file__).resolve().parent.parent / "img" / "first-logo-design.png"
            if img_path.exists() and HAS_PIL:
                tray_img = Image.open(img_path).resize((64, 64), Image.LANCZOS)
            else:
                tray_img = Image.new("RGB", (64, 64), theme.ACCENT)

            def show_window(icon, item):
                self.root.after(0, self._show_window)

            def quit_app(icon, item):
                self.root.after(0, self._exit)

            menu = (TrayItem(self._t("tray.show"), show_window, default=True),
                    TrayItem(self._t("tray.quit"), quit_app))
            self.tray_icon = pystray.Icon(__app_name__, tray_img,
                                          f"{__app_name__} v{__version__}", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception:  # noqa: BLE001
            self.tray_icon = None

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _open_github(self):
        try:
            if sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", GITHUB_URL])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", GITHUB_URL])
            else:  # windows
                os.startfile(GITHUB_URL)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass

    def _on_close(self):
        if self.processor.is_running:
            self.processor.cancel()
        self._closing = True
        if getattr(self, "tray_icon", None):
            self.root.withdraw()
            return
        self._exit()

    def _exit(self):
        self._closing = True
        try:
            if getattr(self, "tray_icon", None):
                self.tray_icon.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            if self._ticker:
                self.root.after_cancel(self._ticker)
        except Exception:  # noqa: BLE001
            pass
        self.root.quit()
        self.root.destroy()
        os._exit(0)

    def run(self):
        self.root.mainloop()


def run(lang: str = None):
    App(lang=lang).run()
