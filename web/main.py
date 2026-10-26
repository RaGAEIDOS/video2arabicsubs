"""FastAPI backend + static frontend for Video2ArabicSubs.

Run with:

    uvicorn web.main:app --reload

Endpoints
---------
* ``GET  /``                    — the SPA (drag&drop, editor, player)
* ``GET  /api/health``          — capabilities for the UI
* ``POST /api/upload``          — multipart upload + processing options → job_id
* ``POST /api/url``             — video URL ingestion (requires yt-dlp)
* ``GET  /api/status/{id}``     — JSON snapshot of a job (polling fallback)
* ``GET  /api/events/{id}``     — SSE stream of live progress
* ``GET  /api/subtitles/{id}``  — parsed cues (editor)
* ``PUT  /api/subtitles/{id}``  — save edited cues
* ``GET  /api/download/{id}``   — UTF-8 ``.srt`` / ``.vtt`` / burned video
* ``GET  /api/video/{id}``      — the uploaded video (Range-aware, for <video>)
* ``POST /api/cancel/{id}``     — cancel a running job
* ``POST /api/job/{id}/retry``  — re-run a failed/cancelled job (resumes caches)
* ``DELETE /api/job/{id}``      — cancel + delete job data immediately
"""
from __future__ import annotations

import asyncio
import mimetypes
import os
import queue
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from core import subtitles
from core.models import Cue, JobOptions, Stage, LANGUAGES, MODEL_SIZES, ENGINES, OUTPUT_FORMATS
from core.pipeline import burn_status
from web import jobs as jobs_module
from web.jobs import dumps, manager, url_support
from web.schemas import SubtitleUpdate

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"

MAX_UPLOAD_MB = int(os.environ.get("V2A_MAX_UPLOAD_MB", "2048"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MULTIPART_OVERHEAD = 2 * 1024 * 1024

VIDEO_EXTENSIONS = (
    ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm",
    ".mpg", ".mpeg", ".m4v", ".3gp", ".ts", ".mts", ".vob",
    ".ogg", ".ogv", ".mxf", ".mpv", ".asf",
)
AUDIO_EXTENSIONS = (
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".opus", ".wma", ".oga",
)
ALLOWED_EXTENSIONS = set(VIDEO_EXTENSIONS + AUDIO_EXTENSIONS)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    manager.start_sweeper()
    yield
    manager.stop()


app = FastAPI(title="Video2ArabicSubs API", version=__version__, lifespan=lifespan)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if (ROOT / "img").is_dir():
    app.mount("/img", StaticFiles(directory=ROOT / "img"), name="img")


# ── helpers ───────────────────────────────────────────────────────────────
def _require_job(job_id: str) -> "jobs_module.Job":
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job id")
    return job


def _build_options(
    model_size: str,
    source_language: str,
    engine: str,
    output_format: str,
    burn_video: bool,
    add_bom: bool,
) -> JobOptions:
    try:
        return JobOptions(
            model_size=model_size,
            source_language=source_language,
            engine=engine,
            output_format=output_format,
            burn_video=bool(burn_video),
            add_bom=bool(add_bom),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _sse(payload: dict, event: Optional[str] = None) -> str:
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {dumps(payload)}\n\n"


def _attachment(filename: str, media_type: str, content: bytes) -> Response:
    ascii_name = filename.encode("ascii", "replace").decode("ascii").replace('"', "_")
    disposition = (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(filename, safe='')}"
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": disposition},
    )


def _tailor_bytes(job: "jobs_module.Job", fmt: str, bom: bool) -> bytes:
    text = subtitles.serialize(job.cues or [], fmt)
    return text.encode("utf-8-sig" if bom else "utf-8")


# ── app / static ──────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "version": __version__,
        "models": list(MODEL_SIZES),
        "engines": list(ENGINES),
        "output_formats": list(OUTPUT_FORMATS),
        "languages": LANGUAGES,
        "video_extensions": list(VIDEO_EXTENSIONS),
        "audio_extensions": list(AUDIO_EXTENSIONS),
        "max_upload_mb": MAX_UPLOAD_MB,
        "url_support": url_support(),
        "burn": burn_status(),
        "defaults": {
            "model_size": "small",
            "source_language": "auto",
            "engine": "google",
            "output_format": "both",
        },
    }


# ── jobs ──────────────────────────────────────────────────────────────────
def _clean_output_dir(value: str) -> Optional[str]:
    """Validate the user-chosen save folder (created eagerly → fails fast)."""
    value = (value or "").strip()
    if not value:
        return None
    if len(value) > 500:
        raise HTTPException(status_code=400, detail="Save folder path is too long")
    path = Path(value).expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
        path = path.resolve()
    except OSError as exc:
        raise HTTPException(
            status_code=400, detail=f"Cannot use the save folder: {exc}"
        ) from exc
    return str(path)


@app.post("/api/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    model_size: str = Form("small"),
    source_language: str = Form("auto"),
    engine: str = Form("google"),
    output_format: str = Form("both"),
    burn_video: bool = Form(False),
    add_bom: bool = Form(False),
    output_dir: str = Form(""),
) -> dict:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_UPLOAD_BYTES + MULTIPART_OVERHEAD:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large (limit {MAX_UPLOAD_MB} MB)",
                )
        except ValueError:
            pass

    filename = os.path.basename(file.filename or "").strip() or "video"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext or '(no extension)'}'",
        )

    options = _build_options(
        model_size, source_language, engine, output_format, burn_video, add_bom
    )
    job = manager.create(
        options=options,
        source="upload",
        original_filename=filename,
        output_dir=_clean_output_dir(output_dir),
    )

    dest = job.dir / f"source{ext}"
    written = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large (limit {MAX_UPLOAD_MB} MB)",
                    )
                out.write(chunk)
        if written == 0:
            raise HTTPException(status_code=400, detail="Empty file")
    except BaseException:
        manager.delete(job.id)
        raise

    job.media_path = dest
    job.add_log(f"Uploaded {filename} ({written / (1024 * 1024):.1f} MB)")
    manager.start(job)
    return {"job_id": job.id}


@app.post("/api/url")
async def upload_url(
    url: str = Form(...),
    model_size: str = Form("small"),
    source_language: str = Form("auto"),
    engine: str = Form("google"),
    output_format: str = Form("both"),
    burn_video: bool = Form(False),
    add_bom: bool = Form(False),
    output_dir: str = Form(""),
) -> dict:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="Only http(s) URLs are supported")
    if not url_support():
        raise HTTPException(
            status_code=501,
            detail="URL ingestion requires yt-dlp — install it with: pip install yt-dlp",
        )
    options = _build_options(
        model_size, source_language, engine, output_format, burn_video, add_bom
    )
    job = manager.create(
        options=options,
        source="url",
        original_filename=url,
        output_dir=_clean_output_dir(output_dir),
    )
    job.url = url
    job.add_log(f"Queued URL: {url}")
    manager.start(job)
    return {"job_id": job.id}


@app.get("/api/jobs")
def list_jobs() -> dict:
    return {"jobs": [job.snapshot() for job in manager.list_jobs()]}


@app.get("/api/status/{job_id}")
def job_status(job_id: str) -> dict:
    return _require_job(job_id).snapshot()


@app.get("/api/events/{job_id}")
async def job_events(job_id: str, request: Request) -> StreamingResponse:
    job = _require_job(job_id)
    subscriber = job.subscribe()

    async def generator():
        try:
            yield _sse({"type": "snapshot", **job.snapshot()})
            if job.is_terminal:
                yield _sse(
                    {
                        "type": "end",
                        "stage": job.stage.value,
                        "percent": round(job.percent, 1),
                        "error": job.error,
                    }
                )
                return
            while True:
                if await request.is_disconnected():
                    return
                try:
                    item = await asyncio.to_thread(subscriber.get, True, 15.0)
                except queue.Empty:
                    yield ": keepalive\n\n"
                    continue
                if item is None:
                    yield _sse({"type": "eof"})
                    return
                yield _sse(item)
        finally:
            job.unsubscribe(subscriber)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/cancel/{job_id}")
def cancel_job(job_id: str) -> dict:
    job = _require_job(job_id)
    job.cancel_event.set()
    job.add_log("Cancellation requested…")
    return {"ok": True, "job_id": job.id, "stage": job.stage.value}


@app.post("/api/job/{job_id}/retry")
def retry_job(job_id: str) -> dict:
    """Re-run a failed/cancelled job, resuming from the cached transcript
    and partial translations (so a 429-failed translation does not force a
    full re-transcription)."""
    job = _require_job(job_id)
    if job.stage not in (Stage.ERROR, Stage.CANCELLED):
        raise HTTPException(
            status_code=409, detail="Only failed or cancelled jobs can be retried"
        )
    if job.media_path is None or not Path(job.media_path).exists():
        raise HTTPException(
            status_code=410, detail="Source media is no longer available — upload it again"
        )
    if not job.prepare_retry():
        raise HTTPException(
            status_code=409, detail="Only failed or cancelled jobs can be retried"
        )
    manager.start(job)
    return {"ok": True, "job_id": job.id}


@app.delete("/api/job/{job_id}")
def delete_job(job_id: str) -> dict:
    if not manager.delete(job_id):
        raise HTTPException(status_code=404, detail="Unknown job id")
    return {"ok": True, "job_id": job_id}


# ── subtitles ─────────────────────────────────────────────────────────────
@app.get("/api/subtitles/{job_id}")
def get_subtitles(job_id: str) -> dict:
    job = _require_job(job_id)
    if job.cues is None:
        raise HTTPException(
            status_code=409,
            detail=f"Subtitles not ready (stage: {job.stage.value})",
        )
    return {
        "job_id": job.id,
        "language": job.language,
        "duration": job.duration,
        "filename": job.stem,
        "cues": [cue.to_dict() for cue in job.cues],
    }


@app.put("/api/subtitles/{job_id}")
def put_subtitles(job_id: str, body: SubtitleUpdate) -> dict:
    job = _require_job(job_id)
    if job.cues is None:
        raise HTTPException(status_code=409, detail="Subtitles not ready yet")

    cues = []
    for cue in body.cues:
        text = cue.text.strip()
        if not text:
            continue
        cues.append(
            Cue(index=len(cues) + 1, start=float(cue.start), end=float(cue.end), text=text)
        )
    if not cues:
        raise HTTPException(status_code=422, detail="At least one non-empty cue is required")

    with job._lock:
        job.cues = cues
        for fmt in job.options.wanted_formats():
            path = job.dir / f"{job.stem}.{fmt}"
            try:
                subtitles.write_file(cues, str(path), fmt=fmt, bom=job.options.add_bom)
                job.files[fmt] = str(path)
            except OSError:
                pass
        job.updated_at = time.time()
    job.add_log(f"Subtitles edited in the browser — {len(cues)} cue(s)")
    job.copy_outputs()  # keep the user-chosen save folder in sync with edits
    return {"ok": True, "job_id": job.id, "cues": len(cues)}


# ── media / download ──────────────────────────────────────────────────────
@app.get("/api/video/{job_id}")
def get_video(job_id: str) -> FileResponse:
    job = _require_job(job_id)
    if job.media_path is None or not job.media_path.exists():
        raise HTTPException(status_code=404, detail="Media not available")
    media_type = mimetypes.guess_type(str(job.media_path))[0] or "application/octet-stream"
    return FileResponse(job.media_path, media_type=media_type)


@app.get("/api/download/{job_id}")
def download(
    job_id: str,
    format: str = Query("srt", pattern="^(srt|vtt|video)$"),
    bom: Optional[bool] = Query(None),
) -> Response:
    job = _require_job(job_id)
    if job.cues is None:
        raise HTTPException(
            status_code=409,
            detail=f"Subtitles not ready (stage: {job.stage.value})",
        )

    if format == "video":
        video_path = job.files.get("video")
        if not video_path or not Path(video_path).exists():
            raise HTTPException(status_code=404, detail="Burned video not available")
        return FileResponse(
            video_path,
            media_type="video/mp4",
            filename=f"{job.stem}.subtitled.mp4",
        )

    use_bom = job.options.add_bom if bom is None else bool(bom)
    content = _tailor_bytes(job, format, use_bom)
    media_type = (
        "application/x-subrip; charset=utf-8"
        if format == "srt"
        else "text/vtt"
    )
    return _attachment(f"{job.stem}.{format}", media_type, content)


if __name__ == "__main__":  # convenience: python -m web.main
    import uvicorn

    uvicorn.run("web.main:app", host="127.0.0.1", port=8000, reload=False)
