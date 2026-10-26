"""In-memory job registry: background workers, SSE fan-out, TTL cleanup.

Design notes
------------
* Jobs run in daemon **threads** — Whisper/torch is native-code bound, so
  threads behave well and avoid multiprocessing pickling entirely.
* ``V2A_MAX_CONCURRENT`` (default ``1``) serializes heavy transcription.
* Each job owns a directory under ``web/data/jobs/{id}/`` holding the
  upload, subtitle outputs and (optionally) the burned video; it is removed
  when the job is deleted or after ``V2A_JOB_TTL`` seconds of inactivity.
* Progress is fanned out to any number of SSE subscribers through
  thread-safe :mod:`queue` queues (``None`` marks end-of-stream).
"""
from __future__ import annotations

import importlib.util
import json
import os
import queue
import shutil
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from core.models import (
    Cue,
    JobOptions,
    PipelineCancelled,
    ProgressEvent,
    Stage,
    StageError,
    TERMINAL_STAGES,
)
from core.pipeline import run_pipeline

DATA_DIR = Path(os.environ.get("V2A_DATA_DIR") or (Path(__file__).resolve().parent / "data"))
JOBS_DIR = DATA_DIR / "jobs"
JOB_TTL_SECONDS = int(os.environ.get("V2A_JOB_TTL", "1800"))
MAX_CONCURRENT_JOBS = max(1, int(os.environ.get("V2A_MAX_CONCURRENT", "1")))
MAX_LOG_LINES = 500
SNIFF_LOG_TAIL = 150
SWEEP_INTERVAL_SECONDS = 60
DOWNLOAD_PREVIEW_PERCENT = 10.0  # URL-download occupies job percent 0–10


def url_support() -> bool:
    """True when ``yt-dlp`` is installed and ``POST /api/url`` can work."""
    try:
        return importlib.util.find_spec("yt_dlp") is not None
    except (ImportError, ValueError):
        return False


class Job:
    def __init__(
        self,
        options: JobOptions,
        source: str,
        original_filename: str,
        job_dir: Path,
        output_dir: Optional[str] = None,
    ):
        self.id = uuid.uuid4().hex
        self.options = options
        self.source = source                      # "upload" | "url"
        self.url = ""                             # when source == "url"
        self.original_filename = original_filename
        stem = Path(original_filename or "video").stem.strip() or "video"
        self.stem = "".join(ch if ch.isalnum() or ch in " -_()" else "_" for ch in stem)[:120]
        self.dir = job_dir
        # Optional user-chosen folder that receives the generated files.
        self.output_dir: Optional[str] = (output_dir or "").strip() or None

        self.stage: Stage = Stage.QUEUED
        self.percent: float = 0.0
        self.stage_percent: Optional[float] = None
        self.message: str = ""
        self.error: Optional[str] = None
        self.warnings: List[str] = []
        self.logs: List[str] = []
        self.language: Optional[str] = None
        self.duration: Optional[float] = None
        self.cues: Optional[List[Cue]] = None
        self.files: Dict[str, str] = {}           # srt / vtt / video → abs path
        self.media_path: Optional[Path] = None

        self.created_at = time.time()
        self.updated_at = self.created_at
        self.cancel_event = threading.Event()

        self._lock = threading.RLock()
        self._subscribers: List["queue.Queue"] = []

    # ── state ─────────────────────────────────────────────────────────
    @property
    def is_terminal(self) -> bool:
        return self.stage in TERMINAL_STAGES

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "job_id": self.id,
                "stage": self.stage.value,
                "percent": round(self.percent, 1),
                "stage_percent": None if self.stage_percent is None else round(self.stage_percent, 4),
                "message": self.message,
                "error": self.error,
                "warnings": list(self.warnings),
                "logs": self.logs[-SNIFF_LOG_TAIL:],
                "language": self.language,
                "duration": self.duration,
                "original_filename": self.original_filename,
                "source": self.source,
                "output_dir": self.output_dir,
                "options": self.options.to_dict(),
                "has_subtitles": self.cues is not None,
                "files": sorted(self.files.keys()),
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }

    # ── mutation + publish ────────────────────────────────────────────
    def prepare_retry(self) -> bool:
        """Reset a failed/cancelled job so it can run again (resumable).

        Returns ``False`` when the job is not in a retryable state. The job
        directory (upload + resume caches) is kept, so the pipeline skips
        already-completed stages.
        """
        with self._lock:
            if self.stage not in (Stage.ERROR, Stage.CANCELLED):
                return False
            self.stage = Stage.QUEUED
            self.percent = 0.0
            self.stage_percent = None
            self.message = ""
            self.error = None
            self.warnings = []
            self.cues = None
            self.files = {}
            self.cancel_event = threading.Event()  # the old event may be set
            self.updated_at = time.time()
            self._append_log("↻ Retrying — resuming from cached progress…", self.updated_at)
        return True

    def _append_log(self, text: str, ts: float) -> None:
        self.logs.append(text)
        if len(self.logs) > MAX_LOG_LINES:
            del self.logs[: len(self.logs) - MAX_LOG_LINES]
        self._publish({"type": "log", "text": text, "ts": ts})

    def add_log(self, text: str) -> None:
        with self._lock:
            self.updated_at = time.time()
            self._append_log(text, self.updated_at)

    def copy_outputs(self) -> None:
        """Copy the generated files into the user-chosen save folder."""
        if not self.output_dir:
            return
        dest = Path(self.output_dir)
        try:
            dest.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.add_log(f"⚠ Save folder not usable: {exc}")
            return
        copied: List[str] = []
        for src in list(self.files.values()):
            src_path = Path(src)
            if not src_path.exists():
                continue
            try:
                shutil.copy2(src_path, dest / src_path.name)
                copied.append(src_path.name)
            except OSError as exc:
                self.add_log(f"⚠ Could not copy {src_path.name} to the save folder: {exc}")
        if copied:
            self.add_log(f"💾 Saved to {dest}: {', '.join(copied)}")

    def apply_event(self, event: ProgressEvent) -> None:
        """Consume a :class:`ProgressEvent` emitted by the pipeline."""
        with self._lock:
            self.stage = event.stage
            self.percent = event.percent
            self.stage_percent = event.stage_percent
            if event.message:
                self.message = event.message
            self.updated_at = time.time()
            if event.message:
                self._append_log(event.message, self.updated_at)
            self._publish(
                {
                    "type": "progress",
                    "stage": self.stage.value,
                    "percent": round(self.percent, 1),
                    "stage_percent": None
                    if self.stage_percent is None
                    else round(self.stage_percent, 4),
                    "message": event.message,
                    "ts": self.updated_at,
                }
            )

    def set_stage(self, stage: Stage, percent: Optional[float] = None, message: str = "") -> None:
        with self._lock:
            self.stage = stage
            if percent is not None:
                self.percent = percent
            if message:
                self.message = message
            self.updated_at = time.time()
            if message:
                self._append_log(message, self.updated_at)
            self._publish(
                {
                    "type": "progress",
                    "stage": self.stage.value,
                    "percent": round(self.percent, 1),
                    "stage_percent": None,
                    "message": message,
                    "ts": self.updated_at,
                }
            )

    def set_terminal(self, stage: Stage, error: Optional[str] = None, log: str = "") -> None:
        """Mark the job finished (done/error/cancelled) and end all streams."""
        with self._lock:
            if self.is_terminal:
                return
            self.stage = stage
            self.error = error
            if stage == Stage.DONE:
                self.percent = 100.0
                self.stage_percent = 1.0
            if log:
                self.message = log
                self._append_log(log, time.time())
            self.updated_at = time.time()
            self._publish(
                {
                    "type": "end",
                    "stage": self.stage.value,
                    "percent": round(self.percent, 1),
                    "error": self.error,
                    "ts": self.updated_at,
                }
            )
            for q in list(self._subscribers):  # end-of-stream sentinel
                self._offer(q, None)

    # ── SSE subscribers ───────────────────────────────────────────────
    def subscribe(self) -> "queue.Queue":
        q: "queue.Queue" = queue.Queue(maxsize=256)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: "queue.Queue") -> None:
        with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    @staticmethod
    def _offer(q: "queue.Queue", item) -> None:
        try:
            q.put_nowait(item)
        except queue.Full:  # slow consumer → drop oldest, keep the stream fresh
            try:
                q.get_nowait()
            except queue.Empty:
                pass
            try:
                q.put_nowait(item)
            except queue.Full:
                pass

    def _publish(self, payload: dict) -> None:
        for q in list(self._subscribers):
            self._offer(q, payload)


class JobManager:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self._semaphore = threading.Semaphore(MAX_CONCURRENT_JOBS)
        self._sweeper_stop = threading.Event()
        self._sweeper: Optional[threading.Thread] = None

    # ── lifecycle ─────────────────────────────────────────────────────
    def wipe_storage(self) -> None:
        """Fresh start: job registry is in-memory, so old files are stale."""
        shutil.rmtree(JOBS_DIR, ignore_errors=True)
        JOBS_DIR.mkdir(parents=True, exist_ok=True)

    def start_sweeper(self) -> None:
        self.wipe_storage()
        if self._sweeper is None:
            self._sweeper = threading.Thread(
                target=self._sweep_loop, daemon=True, name="job-sweeper"
            )
            self._sweeper.start()

    def stop(self) -> None:
        self._sweeper_stop.set()

    def _sweep_loop(self) -> None:
        while not self._sweeper_stop.wait(SWEEP_INTERVAL_SECONDS):
            try:
                self.sweep()
            except Exception:  # noqa: BLE001 — sweeper must never die
                pass

    def sweep(self, now: Optional[float] = None) -> int:
        """Delete terminal jobs idle longer than the TTL. Returns #removed."""
        now = now or time.time()
        removed = 0
        for job in self.list_jobs():
            if job.is_terminal and (now - job.updated_at) > JOB_TTL_SECONDS:
                self.delete(job.id)
                removed += 1
        return removed

    # ── registry ──────────────────────────────────────────────────────
    def create(
        self,
        options: JobOptions,
        source: str,
        original_filename: str,
        output_dir: Optional[str] = None,
    ) -> Job:
        with self._lock:
            job_id = uuid.uuid4().hex
            job_dir = JOBS_DIR / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            job = Job(options, source, original_filename, job_dir, output_dir=output_dir)
            job.id = job_id
            self._jobs[job.id] = job
            return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> List[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def delete(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.pop(job_id, None)
        if job is None:
            return False
        job.cancel_event.set()
        with job._lock:
            for q in list(job._subscribers):
                self._offer(q, None)
            job._subscribers.clear()
        shutil.rmtree(job.dir, ignore_errors=True)
        return True

    def start(self, job: Job) -> None:
        threading.Thread(
            target=self._run, args=(job,), daemon=True, name=f"job-{job.id[:8]}"
        ).start()

    # ── worker ────────────────────────────────────────────────────────
    def _acquire_slot(self, job: Job) -> bool:
        while True:
            if job.cancel_event.is_set():
                return False
            if self._semaphore.acquire(timeout=0.5):
                return True
            job.updated_at = time.time()  # keep queued jobs out of the TTL sweep

    def _run(self, job: Job) -> None:
        if not self._acquire_slot(job):
            job.set_terminal(Stage.CANCELLED, log="Cancelled while queued")
            return
        try:
            if job.cancel_event.is_set():
                job.set_terminal(Stage.CANCELLED, log="Cancelled while queued")
                return

            if job.source == "url" and not (
                job.media_path and Path(job.media_path).exists()
            ):
                job.set_stage(Stage.DOWNLOADING, percent=0.0, message="Downloading video…")
                self._download_url(job)
                if job.cancel_event.is_set():
                    raise PipelineCancelled()

            offset = DOWNLOAD_PREVIEW_PERCENT if job.source == "url" else 0.0
            scale = 100.0 - offset
            result = run_pipeline(
                str(job.media_path),
                str(job.dir),
                job.options,
                base_name=job.stem,
                on_event=job.apply_event,
                cancel_event=job.cancel_event,
                progress_offset=offset,
                progress_scale=scale,
                cache_dir=str(job.dir),
            )

            with job._lock:
                job.cues = result.cues
                job.files = result.files
                job.language = result.language
                job.duration = result.duration
                job.warnings = result.warnings
            for warning in result.warnings:
                job.add_log(f"⚠ {warning}")
            job.copy_outputs()  # results land in the user-chosen save folder
            job.set_terminal(Stage.DONE, log=f"Done — {len(result.cues)} subtitle cue(s)")

        except PipelineCancelled:
            job.set_terminal(Stage.CANCELLED, log="❌ Cancelled")
        except StageError as exc:
            job.set_terminal(
                Stage.ERROR,
                error=f"[{exc.stage.value}] {exc.message}",
                log=f"❌ [{exc.stage.value}] {exc.message}",
            )
            job.add_log(exc.traceback_text().rstrip())
        except Exception as exc:  # noqa: BLE001
            job.set_terminal(Stage.ERROR, error=str(exc), log=f"❌ {exc}")
            job.add_log(traceback.format_exc().rstrip())
        finally:
            self._semaphore.release()

    def _download_url(self, job: Job) -> None:
        if not url_support():
            raise StageError(
                Stage.DOWNLOADING,
                "URL ingestion requires yt-dlp (pip install yt-dlp)",
            )
        import yt_dlp

        last_publish = [0.0]

        def hook(d) -> None:
            if job.cancel_event.is_set():
                raise yt_dlp.utils.DownloadCancelled("cancelled")
            if d.get("status") != "downloading":
                return
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            if not total:
                return
            fraction = min(1.0, done / total)
            now = time.time()
            if now - last_publish[0] < 0.4:
                return
            last_publish[0] = now
            job.set_stage(
                Stage.DOWNLOADING,
                percent=DOWNLOAD_PREVIEW_PERCENT * fraction,
                message="",
            )

        opts = {
            "outtmpl": str(job.dir / "source.%(ext)s"),
            "format": "best[ext=mp4]/best",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [hook],
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([job.url])
        except PipelineCancelled:
            raise
        except Exception as exc:  # noqa: BLE001
            if job.cancel_event.is_set():
                raise PipelineCancelled() from exc
            raise StageError(Stage.DOWNLOADING, f"Download failed: {exc}", exc) from exc

        candidates = sorted(
            (p for p in job.dir.glob("source.*") if not p.name.endswith(".part")),
            key=lambda p: p.stat().st_size,
            reverse=True,
        )
        if not candidates:
            raise StageError(Stage.DOWNLOADING, "Download produced no file")
        job.media_path = candidates[0]
        job.add_log(f"Downloaded: {candidates[0].name}")


#: Singleton used by the FastAPI routes.
manager = JobManager()


def dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)
