"""M9 macro — background bridge between the Tkinter GUI and the core engine.

Design (this is the “ما يعلقش أو يهنج” contract for the desktop app):

* **All heavy work runs on a daemon thread** — Whisper/Argos/FFmpeg never
  touch the Tk thread,
* the worker communicates **only through a ``queue.Queue`` of structured
  event dicts**; the GUI drains that queue from a ``root.after`` ticker —
  no ``update()``-spinning, no cross-thread widget calls,
* each processing concern is delegated to its own core macro
  (:mod:`core.batch` for the ordered list, :mod:`core.pipeline` per file),
* the processor emits **stage enums**, not sentences, so the GUI can render
  them in the active language (Arabic/English) at paint time.

Usage::

    proc = Processor()
    proc.start(video_paths, options, order="path")
    # …in the GUI ticker:
    for event in proc.drain():
        handle(event)
"""
from __future__ import annotations

import os
import queue
import threading
import traceback
from typing import Dict, List, Optional

from core import batch as batch_mod
from core.models import JobOptions, PipelineCancelled, Stage


class Processor:
    """Runs an ordered batch of videos on a background thread."""

    def __init__(self):
        self.events: "queue.Queue[dict]" = queue.Queue()
        self._cancel = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ── lifecycle ──────────────────────────────────────────────────────
    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(
        self,
        video_paths: List[str],
        options: JobOptions,
        order: str = "given",
        recursive: bool = False,
    ) -> bool:
        """Kick off a batch. Returns ``False`` when a run is already active."""
        if self.is_running:
            return False
        self._cancel.clear()
        # Drop any stale events from a previous run.
        while True:
            try:
                self.events.get_nowait()
            except queue.Empty:
                break
        self._thread = threading.Thread(
            target=self._run,
            args=(list(video_paths), options, order, recursive),
            daemon=True,
            name="v2a-processor",
        )
        self._thread.start()
        return True

    def cancel(self) -> None:
        self._cancel.set()

    def drain(self, limit: int = 200) -> List[dict]:
        """Non-blocking: pull every queued event (called from the GUI ticker)."""
        out: List[dict] = []
        for _ in range(limit):
            try:
                out.append(self.events.get_nowait())
            except queue.Empty:
                break
        return out

    def _emit(self, payload: dict) -> None:
        try:
            self.events.put_nowait(payload)
        except Exception:  # noqa: BLE001
            pass

    # ── worker ─────────────────────────────────────────────────────────
    def _run(self, paths: List[str], options: JobOptions, order: str,
             recursive: bool) -> None:
        total = len(paths)

        def on_item(ev: batch_mod.BatchItemEvent) -> None:
            self._emit({"type": "item", "event": ev})

        def on_event(evt) -> None:
            self._emit(
                {
                    "type": "progress",
                    "stage": evt.stage,
                    "percent": evt.percent,
                    "stage_percent": evt.stage_percent,
                    "message": evt.message,
                }
            )

        self._emit({"type": "batch_start", "total": total})
        try:
            result = batch_mod.run_batch(
                paths,
                options,
                output_dir=None,          # subtitles land next to each video
                order=order,
                recursive=recursive,
                on_item=on_item,
                on_event=on_event,
                cancel_event=self._cancel,
            )
        except Exception as exc:  # noqa: BLE001 — surface, never crash the thread
            self._emit({"type": "fatal", "error": str(exc),
                        "traceback": traceback.format_exc()})
            return
        finally:
            self._cancel.clear()

        self._emit(
            {
                "type": "batch_end",
                "done": list(result.done),
                "failed": list(result.failed),
                "cancelled": result.cancelled,
                "total": total,
            }
        )


# ── helpers shared with the CLI / GUI ────────────────────────────────────
def default_options(
    model_size: str = "small",
    engine: str = "argos",
    output_format: str = "both",
    burn_video: bool = False,
    add_credit: bool = True,
    add_bom: bool = False,
    source_language: str = "auto",
) -> JobOptions:
    """Build a validated :class:`JobOptions` from raw UI values."""
    return JobOptions(
        model_size=model_size,
        source_language=source_language,
        engine=engine,
        output_format=output_format,
        burn_video=bool(burn_video),
        add_bom=bool(add_bom),
        add_credit=bool(add_credit),
        save_next_to_video=True,
    )
