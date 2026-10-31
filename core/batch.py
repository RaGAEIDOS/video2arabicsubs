"""M3 macro — ordered batch translation of a *path* (folder or file list).

This is the module that powers the core user story:

    «ترجم عدد من الفيديوهات في مسار معيّن — بالترتيب — واحدة تلو الأخرى».

Everything here is deliberately isolated from any UI:

* ``scan_video_files``  — collect videos from a folder (optionally
  recursive) and sort them with a **natural** ordering of the path, so
  ``video2.mp4`` comes before ``video10.mp4`` and ``EP2`` before ``EP10``,
* ``sort_paths``        — natural-sort an explicit user-provided list
  (the ▲▼ arrows in the GUI can still override the order),
* ``run_batch``         — process the list **sequentially** in a worker
  thread-friendly way (it never touches a GUI toolkit), emitting a
  structured :class:`BatchItemEvent` per file and mapping the whole batch
  onto a single 0–100 % progress range.

It runs fine on a background thread (the desktop app and the future CLI do
exactly that) and honours a ``threading.Event`` for cooperative
cancellation between files.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

from core.models import JobOptions, PipelineCancelled, ProgressEvent, Stage, StageError
from core.pipeline import run_pipeline

#: Video extensions accepted when scanning a folder.
VIDEO_EXTENSIONS = (
    ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm",
    ".mpg", ".mpeg", ".m4v", ".3gp", ".ts", ".mts", ".vob",
    ".ogg", ".ogv", ".mxf", ".mpv", ".asf",
)

_CHUNK_RE = re.compile(r"(\d+)")


def natural_key(path: str) -> List:
    """Natural-sort key: ``ep2`` < ``ep10``, case-insensitive, path aware."""
    parts = _CHUNK_RE.split(os.path.normpath(path))
    key: List = []
    for part in parts:
        if part.isdigit():
            key.append((1, int(part), ""))
        elif part:
            key.append((0, 0, part.casefold()))
    return key


def sort_paths(paths: Sequence[str]) -> List[str]:
    """Return ``paths`` sorted naturally by their full path."""
    return sorted((str(p) for p in paths), key=natural_key)


def is_video(path: str) -> bool:
    return os.path.splitext(str(path))[1].lower() in VIDEO_EXTENSIONS


def scan_video_files(folder: str, recursive: bool = False) -> List[str]:
    """All video files inside ``folder`` in natural path order.

    ``recursive`` walks sub-folders too (still keeping the natural order of
    the whole relative path — the "مجموعات فيديوهات" use-case).
    """
    folder = os.path.abspath(str(folder))
    found: List[str] = []
    if recursive:
        for root, _dirs, files in os.walk(folder):
            for name in files:
                if is_video(name):
                    found.append(os.path.join(root, name))
    else:
        try:
            entries = os.listdir(folder)
        except OSError:
            return []
        for name in entries:
            full = os.path.join(folder, name)
            if is_video(full) and os.path.isfile(full):
                found.append(full)
    return sort_paths(found)


# ── Events ────────────────────────────────────────────────────────────────
@dataclass
class BatchItemEvent:
    """Structured per-file notification (the UI only reads these)."""

    kind: str                      # "item_start" | "item_done" | "item_error" | "item_cancelled"
    index: int                     # 0-based position in the batch
    total: int
    path: str
    name: str
    files: Dict[str, str] = field(default_factory=dict)  # srt/vtt/video → path
    error: str = ""
    stage: Optional[Stage] = None
    language: str = ""
    cues: int = 0

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "index": self.index,
            "total": self.total,
            "path": self.path,
            "name": self.name,
            "files": dict(self.files),
            "error": self.error,
            "stage": self.stage.value if self.stage else None,
            "language": self.language,
            "cues": self.cues,
        }


@dataclass
class BatchResult:
    """Summary of a whole batch run."""

    done: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    cancelled: bool = False

    @property
    def ok(self) -> bool:
        return not self.failed and not self.cancelled


def run_batch(
    paths: Sequence[str],
    options: Optional[JobOptions] = None,
    output_dir: Optional[str] = None,
    *,
    order: str = "path",              # "path" (natural sort) | "given" (keep as-is)
    recursive: bool = False,
    on_item: Optional[Callable[[BatchItemEvent], None]] = None,
    on_event: Optional[Callable[[ProgressEvent], None]] = None,
    cancel_event=None,
) -> BatchResult:
    """Translate every video in ``paths`` sequentially, in order.

    * ``order="path"`` re-sorts the list naturally (the folder-order
      behaviour); pass ``order="given"`` when the user rearranged the list
      with the ▲▼ buttons,
    * a failing file does **not** abort the batch — it is recorded and the
      loop continues with the next video,
    * ``on_item`` receives one :class:`BatchItemEvent` per file,
      ``on_event`` receives pipeline :class:`ProgressEvent` objects remapped
      so the whole batch occupies 0–100 %.
    """
    options = options or JobOptions()
    items = sort_paths(paths) if order == "path" else [str(p) for p in paths]
    total = len(items)
    result = BatchResult()

    def _emit(event: Optional[Callable[[BatchItemEvent], None]], payload: BatchItemEvent) -> None:
        if event is None:
            return
        try:
            event(payload)
        except Exception:  # noqa: BLE001 — a broken UI hook must not kill the batch
            pass

    for idx, path in enumerate(items):
        if cancel_event is not None and cancel_event.is_set():
            result.cancelled = True
            break

        name = os.path.basename(path)
        slot = 100.0 / total
        offset = idx * slot

        _emit(
            on_item,
            BatchItemEvent(kind="item_start", index=idx, total=total, path=path, name=name),
        )

        # Remap this file's 0–100 % into its slice of the overall progress.
        def _pipe_event(evt: ProgressEvent, _off=offset, _slot=slot) -> None:
            if on_event is None:
                return
            try:
                on_event(
                    ProgressEvent(
                        stage=evt.stage,
                        percent=_off + _slot * max(0.0, min(100.0, evt.percent)) / 100.0,
                        stage_percent=evt.stage_percent,
                        message=evt.message,
                    )
                )
            except Exception:  # noqa: BLE001
                pass

        try:
            pipe_result = run_pipeline(
                path,
                output_dir,
                options,
                on_event=_pipe_event,
                cancel_event=cancel_event,
                progress_offset=offset,
                progress_scale=slot,
            )
        except PipelineCancelled:
            result.cancelled = True
            _emit(
                on_item,
                BatchItemEvent(
                    kind="item_cancelled", index=idx, total=total, path=path, name=name
                ),
            )
            break
        except StageError as exc:
            result.failed.append(path)
            _emit(
                on_item,
                BatchItemEvent(
                    kind="item_error",
                    index=idx,
                    total=total,
                    path=path,
                    name=name,
                    error=exc.message,
                    stage=exc.stage,
                ),
            )
            continue
        except Exception as exc:  # noqa: BLE001 — never let one file kill the batch
            result.failed.append(path)
            _emit(
                on_item,
                BatchItemEvent(
                    kind="item_error",
                    index=idx,
                    total=total,
                    path=path,
                    name=name,
                    error=str(exc),
                ),
            )
            continue

        result.done.append(path)
        _emit(
            on_item,
            BatchItemEvent(
                kind="item_done",
                index=idx,
                total=total,
                path=path,
                name=name,
                files=dict(pipe_result.files),
                language=pipe_result.language or "",
                cues=len(pipe_result.cues),
            ),
        )

    return result
