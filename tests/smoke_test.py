"""End-to-end smoke test for the web app — no ML dependencies required.

The heavy stages (moviepy / whisper / deep-translator) are stubbed; the
real FastAPI app, job store, worker threads, SSE stream, subtitle
serialization and download endpoints are exercised for real.

Run:  python tests/smoke_test.py
"""
from __future__ import annotations

import io
import os
import shutil
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Fail fast on syntax/import errors of every module.
import app.processor  # noqa: E402,F401
import app.transcriber  # noqa: E402,F401
import core.pipeline  # noqa: E402,F401
import core.translate  # noqa: E402,F401
import web.main  # noqa: E402,F401
from core.models import JobOptions, PipelineCancelled  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# Captured before any test stubs it away — used to exercise the real routing.
REAL_TRANSLATE_BATCH = core.translate.translate_batch

FAKE_SEGMENTS = [
    {"start": 0.0, "end": 2.4, "text": " Hello everyone and welcome back."},
    {"start": 2.4, "end": 5.1, "text": " Today we will learn something new."},
    {"start": 5.1, "end": 5.1, "text": ""},   # empty → must be skipped
    {"start": 5.1, "end": 8.8, "text": " Thank you for watching."},
]
FAKE_TRANSLATIONS = [
    "مرحباً بكم جميعاً وعوداً موفقة",
    "اليوم سوف نتعلم شيئاً جديداً",
    "",
    "شكراً لمشاهدتكم",
]


def fake_extract(video_path, output_dir=None, cancel_event=None):
    wav = os.path.join(output_dir, "fake.wav")
    with open(wav, "wb") as fh:
        fh.write(b"RIFF0000WAVEfmt ")
    return wav


def fake_transcribe(audio_path, model_size="small", language="en",
                    on_progress=None, cancel_event=None):
    if on_progress:
        on_progress(0.5)
    if cancel_event is not None and cancel_event.is_set():
        from core.models import PipelineCancelled
        raise PipelineCancelled()
    time.sleep(0.05)
    if on_progress:
        on_progress(1.0)
    return {"segments": [dict(s) for s in FAKE_SEGMENTS], "language": "en"}


def fake_translate(texts, source="en", target="ar", engine="google",
                   on_progress=None, cancel_event=None, **_kw):
    out = list(texts)
    for i, text in enumerate(texts):
        if text.strip() and i < len(FAKE_TRANSLATIONS):
            out[i] = FAKE_TRANSLATIONS[i]
    if on_progress:
        on_progress(1.0)
    return out


@contextmanager
def stubbed_pipeline():
    with mock.patch("core.audio.extract_audio", side_effect=fake_extract), \
         mock.patch("core.audio.probe_duration", return_value=8.8), \
         mock.patch("core.transcribe.transcribe", side_effect=fake_transcribe), \
         mock.patch("core.translate.translate_batch", side_effect=fake_translate):
        yield


def wait_terminal(client: TestClient, job_id: str, timeout: float = 20.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get(f"/api/status/{job_id}").json()
        if status["stage"] in ("done", "error", "cancelled"):
            return status
        time.sleep(0.1)
    raise AssertionError(f"job {job_id} did not finish in {timeout}s: {status}")


def check(condition: bool, label: str) -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        raise SystemExit(f"ASSERTION FAILED: {label}")


def main() -> None:
    from web.main import app
    from web.jobs import manager

    print("== Translator robustness (batching / retry / resume) ==")

    class FakeGT:
        """Stands in for ``deep_translator.GoogleTranslator`` (records calls)."""

        def __init__(self, mode: str = "ok"):
            self.mode = mode
            self.calls = []

        def translate(self, text: str) -> str:
            self.calls.append(text)
            if self.mode == "rate429" and len(self.calls) == 1:
                raise Exception(
                    "429 Too Many Requests: too many requests to the server"
                )
            if self.mode == "always429":
                raise Exception(
                    "429 Too Many Requests: too many requests to the server"
                )
            if self.mode == "conn_once" and len(self.calls) == 1:
                raise Exception("Connection reset by peer")
            if self.mode == "fatal":
                raise ValueError("invalid source language: xx")
            lines = text.split("\n")
            if self.mode == "bad_join" and len(lines) > 1:
                return "\n".join(f"[ar]{line}" for line in lines) + "\n!!extra"
            return "\n".join(f"[ar]{line}" for line in lines)

    sleeps: list = []

    def translate_with(gt, texts, **kw):
        """Run the real translate_batch against a fake Google + fast clocks.

        These tests exercise the *Google* engine's robustness (batching,
        retry, rate-limit, resume), so they pin ``engine="google"`` — the
        app-wide default is the local engine (see tests/features_test.py).
        """
        sleeps.clear()
        kw.setdefault("engine", "google")
        with mock.patch("core.translate._get_translator", return_value=gt), \
             mock.patch("core.translate.offline_available", return_value=False), \
             mock.patch("core.translate._throttle", side_effect=lambda *a, **k: None), \
             mock.patch("core.translate._sleep",
                        side_effect=lambda s, *a, **k: sleeps.append(s)):
            return core.translate.translate_batch(texts, **kw)

    forty = [f"line {i}" for i in range(40)]
    gt_ok = FakeGT("ok")
    out = translate_with(gt_ok, forty)
    check(len(gt_ok.calls) == 1, "40 segments → ONE Google request (was 40)")
    check(out == [f"[ar]line {i}" for i in range(40)],
          "joined payload split back strictly 1:1")

    gt_join = FakeGT("bad_join")
    out2 = translate_with(gt_join, ["alpha", "beta"])
    check(len(gt_join.calls) == 3, "altered line structure → per-segment fallback")
    check(out2 == ["[ar]alpha", "[ar]beta"], "fallback keeps 1:1 alignment")

    gt_429 = FakeGT("rate429")
    out3 = translate_with(gt_429, ["hello"])
    check(len(gt_429.calls) == 2, "rate-limit (429) retried after backoff")
    check(len(sleeps) == 1 and 5.0 <= sleeps[0] < 6.0,
          "429 backoff ≈ 5s (long rate-limit schedule, first step)")
    check(out3 == ["[ar]hello"], "retry returns the translation")

    gt_block = FakeGT("always429")
    notes: list = []
    try:
        translate_with(gt_block, ["hello"], on_note=notes.append)
        blocked_msg = ""
    except RuntimeError as exc:
        blocked_msg = str(exc)
    check(len(gt_block.calls) == 6, "persistent 429 → 6 attempts on the long schedule")
    check(len(sleeps) == 5 and all(
        core.translate.RATE_LIMIT_DELAYS[i] <= s < core.translate.RATE_LIMIT_DELAYS[i] + 0.6
        for i, s in enumerate(sleeps)),
        "429 waits follow the 5/15/30/60/120s schedule (~4min budget)")
    check("press ↻ Retry" in blocked_msg and "saved" in blocked_msg,
          "give-up message points at the resume button")
    check(len(notes) == 5 and "Rate-limited by Google" in notes[0]
          and "retry 1/5" in notes[0],
          "wait notes exposed to the UI/log")

    gt_conn = FakeGT("conn_once")
    out_conn = translate_with(gt_conn, ["hello"], on_note=lambda _m: None)
    check(len(gt_conn.calls) == 2, "connection blip retried once")
    check(len(sleeps) == 1 and 2.0 <= sleeps[0] < 3.0,
          "non-rate transient errors use the short 2s schedule")
    check(out_conn == ["[ar]hello"], "blip retry returns the translation")

    gt_fatal = FakeGT("fatal")
    try:
        translate_with(gt_fatal, ["hello"])
        raised = ""
    except RuntimeError as exc:
        raised = str(exc)
    check("invalid source" in raised, "permanent error surfaced to the caller")
    check(len(gt_fatal.calls) == 1, "no retry loop on a permanent error")

    stop = threading.Event()
    stop.set()
    gt_cancel = FakeGT("ok")
    cancelled = False
    try:
        translate_with(gt_cancel, ["x"], cancel_event=stop)
    except PipelineCancelled:
        cancelled = True
    check(cancelled and not gt_cancel.calls,
          "cancellation honoured before any request")

    batches: list = []
    gt_known = FakeGT("ok")
    out6 = translate_with(
        gt_known,
        ["one", "two"],
        known={"one": "محفوظة"},
        on_batch=lambda chunk, vals: batches.append((list(chunk), list(vals))),
    )
    check(len(gt_known.calls) == 1, "known (cached) segments are not re-requested")
    check(out6[0] == "محفوظة" and out6[1] == "[ar]two",
          "known + fresh results merged in order")
    check(batches == [(["two"], ["[ar]two"])],
          "on_batch reports fresh pairs for persistence")

    print("== Resume caches (transcript / translations) ==")
    cache_dir = ROOT / "tests" / "_cache_tmp"
    shutil.rmtree(cache_dir, ignore_errors=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    opts_g = JobOptions(engine="google")
    core.pipeline._save_transcript_cache(
        str(cache_dir), "en", 8.8, [{"start": 0, "end": 1, "text": "hi"}]
    )
    tr = core.pipeline._load_transcript_cache(str(cache_dir))
    check(tr is not None and tr["language"] == "en" and len(tr["segments"]) == 1,
          "transcript cache round-trips")
    check(core.pipeline._load_transcript_cache(None) is None,
          "cache_dir=None → caching disabled (desktop path untouched)")
    core.pipeline._save_translation_cache(str(cache_dir), opts_g, "en", {"hi": "مرحبا"})
    check(core.pipeline._load_translation_cache(str(cache_dir), opts_g, "en") == {"hi": "مرحبا"},
          "translation cache round-trips")
    check(core.pipeline._load_translation_cache(str(cache_dir), JobOptions(engine="none"), "en") == {},
          "engine changed → stale translation cache ignored")
    shutil.rmtree(cache_dir, ignore_errors=True)

    print("== Health & static ==")
    with stubbed_pipeline(), TestClient(app) as client:
        health = client.get("/api/health").json()
        check(health["ok"] is True, "GET /api/health → ok")
        check("small" in health["models"], "health lists whisper models")
        check("argos" in health["engines"], "offline engine advertised")
        index = client.get("/")
        check(index.status_code == 200 and b"dropZone" in index.content,
              "GET / serves the SPA")
        check(b"optOutDir" in index.content and b"optLang" not in index.content,
              "UI: save-folder field present, source-language dropdown gone")
        check(b'value="argos"' in index.content, "UI: offline (argos) option present")
        check(b"ghRepo" not in index.content, "UI: GitHub push card removed")
        check(client.get("/static/app.js").status_code == 200, "static assets served")

        print("== Upload validation ==")
        bad = client.post(
            "/api/upload",
            files={"file": ("evil.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
            data={"model_size": "small"},
        )
        check(bad.status_code == 400, "rejects unsupported extension (400)")
        bad2 = client.post(
            "/api/upload",
            files={"file": ("clip.mp4", io.BytesIO(b"x"), "video/mp4")},
            data={"model_size": "not-a-model"},
        )
        check(bad2.status_code == 422, "rejects bad model size (422)")

        out_dir = ROOT / "tests" / "_outdir_tmp"
        shutil.rmtree(out_dir, ignore_errors=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        blocker = out_dir / "blocker.txt"
        blocker.write_text("x", encoding="utf-8")
        bad3 = client.post(
            "/api/upload",
            files={"file": ("clip.mp4", io.BytesIO(b"x"), "video/mp4")},
            data={"model_size": "small", "output_dir": str(blocker / "subs")},
        )
        check(bad3.status_code == 400 and "save folder" in bad3.json()["detail"].lower(),
              "output_dir under a file → 400 fails fast")

        print("== Full happy-path job ==")
        payload = b"\x00\x01\x02" * 4096
        up = client.post(
            "/api/upload",
            files={"file": ("My Video.mp4", io.BytesIO(payload), "video/mp4")},
            data={
                "model_size": "small",
                "source_language": "auto",
                "engine": "google",
                "output_format": "both",
                "burn_video": "false",
                "add_bom": "false",
                "output_dir": str(out_dir),
            },
        )
        check(up.status_code == 200 and "job_id" in up.json(), "POST /api/upload → job_id")
        job_id = up.json()["job_id"]

        status = wait_terminal(client, job_id)
        check(status["stage"] == "done", "job finished with stage=done")
        check(status["percent"] == 100.0, "final percent is 100")
        check(status["has_subtitles"] is True, "has_subtitles flag set")
        check(status["language"] == "en", "detected language returned")
        log_text = "\n".join(status["logs"])
        check("Transcribing" in log_text and "Translating" in log_text,
              "stage log lines recorded")
        check("Saved to" in log_text, "save-folder log line recorded")
        copied_names = sorted(p.name for p in out_dir.iterdir())
        check(any(n.endswith(".srt") for n in copied_names),
              "SRT copied into the save folder")
        check(any(n.endswith(".vtt") for n in copied_names),
              "VTT copied into the save folder")
        saved_srt = next(out_dir.glob("*.srt")).read_text(encoding="utf-8")
        check("مرحباً بكم جميعاً وعوداً موفقة" in saved_srt,
              "copied SRT holds the Arabic text")

        print("== Subtitles API ==")
        subs = client.get(f"/api/subtitles/{job_id}").json()
        # 3 translated cues + 1 promotional credit cue (v0.4) = 4
        check(len(subs["cues"]) == 4, "4 cues (3 real + credit, empty segment skipped)")
        check(subs["cues"][0]["text"].startswith("مرحباً"), "Arabic translation present")
        check(abs(subs["cues"][2]["end"] - 8.8) < 1e-6, "last real cue timing kept")
        check("github.com/RaGAEIDOS/video2arabicsubs" in subs["cues"][-1]["text"],
              "promotional credit cue appended at the end")

        print("== Downloads (UTF-8) ==")
        srt = client.get(f"/api/download/{job_id}", params={"format": "srt"})
        check(srt.status_code == 200, "GET download srt → 200")
        body = srt.content.decode("utf-8")
        check("1\n00:00:00,000 --> 00:00:02,400" in body, "SRT index + timing format")
        check("مرحباً بكم جميعاً وعوداً موفقة" in body, "Arabic text in SRT")
        check("attachment" in srt.headers.get("content-disposition", ""),
              "Content-Disposition attachment")
        check("charset=utf-8" in srt.headers.get("content-type", ""),
              "SRT served as charset=utf-8")

        bom = client.get(f"/api/download/{job_id}",
                         params={"format": "srt", "bom": "true"})
        check(bom.content.startswith(b"\xef\xbb\xbf"), "BOM variant starts with UTF-8 BOM")

        vtt = client.get(f"/api/download/{job_id}", params={"format": "vtt"})
        vtt_text = vtt.content.decode("utf-8")
        check(vtt_text.startswith("WEBVTT"), "VTT header present")
        check("00:00:02.400 --> 00:00:05.100" in vtt_text, "VTT uses dot separator")

        print("== Editor round-trip ==")
        edited = [
            {"start": 0.0, "end": 3.0, "text": "سطر معدل"},
            {"start": 3.0, "end": 9.0, "text": "سطر ثانٍ"},
        ]
        put = client.put(f"/api/subtitles/{job_id}", json={"cues": edited})
        check(put.status_code == 200, "PUT subtitles → 200")
        srt2 = client.get(f"/api/download/{job_id}", params={"format": "srt"})
        check("سطر معدل" in srt2.content.decode("utf-8"), "edited text in new SRT")
        check("00:00:09,000" in srt2.content.decode("utf-8"), "edited timing in new SRT")
        saved_srt2 = next(out_dir.glob("*.srt")).read_text(encoding="utf-8")
        check("سطر معدل" in saved_srt2, "save folder re-synced after the edit")
        bad_put = client.put(f"/api/subtitles/{job_id}",
                             json={"cues": [{"start": 5.0, "end": 1.0, "text": "x"}]})
        check(bad_put.status_code == 422, "end < start rejected (422)")

        print("== Video endpoint ==")
        vid = client.get(f"/api/video/{job_id}")
        check(vid.status_code == 200 and vid.content == payload,
              "GET video returns the uploaded bytes")

        print("== SSE stream (terminal job) ==")
        with client.stream("GET", f"/api/events/{job_id}") as stream:
            chunk = b"".join(stream.iter_bytes()).decode("utf-8", "replace")
        check('"type": "snapshot"' in chunk or '"type":"snapshot"' in chunk,
              "SSE starts with snapshot")
        check('"type": "end"' in chunk or '"type":"end"' in chunk,
              "SSE ends with end event")

        print("== Cancel endpoint (already done → no-op) ==")
        check(client.post(f"/api/cancel/{job_id}").status_code == 200, "cancel → 200")

        print("== Retry & resume (failed translation) ==")
        check(client.post(f"/api/job/{job_id}/retry").status_code == 409,
              "retry a finished job → 409")
        check(client.post("/api/job/no-such-job/retry").status_code == 404,
              "retry unknown job → 404")

        translate_calls = {"n": 0}

        def flaky_translate(texts, **kw):
            translate_calls["n"] += 1
            if translate_calls["n"] == 1:
                raise RuntimeError(
                    "Server Error: You made too many requests to the server "
                    "(429 Too Many Requests)"
                )
            return fake_translate(texts, **kw)

        with mock.patch("core.audio.extract_audio",
                        side_effect=fake_extract) as extract_mock, \
             mock.patch("core.transcribe.transcribe",
                        side_effect=fake_transcribe) as transcribe_mock, \
             mock.patch("core.translate.translate_batch",
                        side_effect=flaky_translate):
            up3 = client.post(
                "/api/upload",
                files={"file": ("retry me.mp4", io.BytesIO(payload), "video/mp4")},
                data={"model_size": "small", "engine": "google"},
            )
            check(up3.status_code == 200, "upload for retry test → 200")
            job3 = up3.json()["job_id"]
            first = wait_terminal(client, job3)
            check(first["stage"] == "error" and "translating" in (first["error"] or ""),
                  "rate-limited translation → stage=error")
            job3_dir = manager.get(job3).dir
            check((job3_dir / "transcript.json").exists(),
                  "transcript cached BEFORE the failure")

            retry = client.post(f"/api/job/{job3}/retry")
            check(retry.status_code == 200, "POST /api/job/{id}/retry → 200")
            second = wait_terminal(client, job3, timeout=30)
            check(second["stage"] == "done", "retry finished with stage=done")
            check(transcribe_mock.call_count == 1,
                  "transcript reused — transcription NOT re-run")
            check(extract_mock.call_count == 1,
                  "audio extraction skipped on retry")
            check(translate_calls["n"] == 2, "translation re-attempted exactly once")
            check((job3_dir / "translations.json").exists(),
                  "translation cache written after success")
            logs3 = "\n".join(second["logs"])
            check("Reused cached transcript" in logs3, "resume logged (transcript reused)")
            check("Retrying" in logs3, "retry logged to the job log")
            check(bool(second["has_subtitles"]), "subtitles produced on retry")
        client.delete(f"/api/job/{job3}")

        print("== Offline engine (argos) ==")
        core.translate.reset_fallback()
        local_calls = {"n": 0}

        def fake_local(chunk, source="en", target="ar", cancel_event=None,
                       on_note=None, **_kw):
            local_calls["n"] += 1
            return fake_translate(list(chunk), source=source, target=target)

        with mock.patch("core.translate.translate_batch", REAL_TRANSLATE_BATCH), \
             mock.patch("core.translate.offline_available", return_value=True), \
             mock.patch("core.translate._offline_translate_batch", side_effect=fake_local):
            up4 = client.post(
                "/api/upload",
                files={"file": ("offline.mp4", io.BytesIO(payload), "video/mp4")},
                data={"model_size": "small", "engine": "argos"},
            )
            check(up4.status_code == 200, "upload with engine=argos → 200")
            job4 = up4.json()["job_id"]
            status4 = wait_terminal(client, job4, timeout=30)
        check(status4["stage"] == "done", "offline engine job → done")
        check(local_calls["n"] >= 1, "offline translator used (Google untouched)")
        subs4 = client.get(f"/api/subtitles/{job4}").json()
        check(bool(subs4["cues"]) and subs4["cues"][0]["text"].startswith("مرحباً"),
              "Arabic subtitles produced offline")
        client.delete(f"/api/job/{job4}")

        print("== Google down → automatic offline fallback ==")
        core.translate.reset_fallback()
        fb_calls = {"n": 0}

        def fb_local(chunk, *args, **kw):
            fb_calls["n"] += 1
            return fake_translate(list(chunk))

        class DeadGoogle:
            """Always rate-limits — the current Google-429 situation."""

            def translate(self, text):
                raise RuntimeError(
                    "429 Too Many Requests: too many requests to the server"
                )

        with mock.patch("core.translate.translate_batch", REAL_TRANSLATE_BATCH), \
             mock.patch("core.translate._get_translator",
                        side_effect=lambda *a, **k: DeadGoogle()), \
             mock.patch.object(core.translate, "RATE_LIMIT_DELAYS", (0.0,)), \
             mock.patch.object(core.translate, "TRANSIENT_DELAYS", (0.0,)), \
             mock.patch("core.translate.offline_available", return_value=True), \
             mock.patch("core.translate._offline_translate_batch", side_effect=fb_local):
            up5 = client.post(
                "/api/upload",
                files={"file": ("google down.mp4", io.BytesIO(payload), "video/mp4")},
                data={"model_size": "small", "engine": "google"},
            )
            check(up5.status_code == 200, "upload with dead Google → 200")
            job5 = up5.json()["job_id"]
            status5 = wait_terminal(client, job5, timeout=30)
        check(status5["stage"] == "done", "job completes despite Google 429 (fallback)")
        check(fb_calls["n"] >= 1, "offline translator took over")
        logs5 = "\n".join(status5["logs"])
        check("switched to the offline translator" in logs5,
              "fallback announced in the job log")
        check(core.translate._google_is_blocked(), "Google cooldown window armed")
        core.translate.reset_fallback()
        check(not core.translate._google_is_blocked(), "cooldown window resettable")
        subs5 = client.get(f"/api/subtitles/{job5}").json()
        check(bool(subs5["cues"]), "fallback job has subtitles")
        client.delete(f"/api/job/{job5}")

        print("== Cleanup ==")
        job_dir = manager.get(job_id).dir
        check(job_dir.exists(), "job dir exists before delete")
        check(client.delete(f"/api/job/{job_id}").status_code == 200, "DELETE job → 200")
        check(not job_dir.exists(), "job dir removed")
        check(next(out_dir.glob("*.srt")).exists(), "save-folder copies survive job deletion")
        shutil.rmtree(out_dir, ignore_errors=True)
        check(client.get(f"/api/status/{job_id}").status_code == 404, "status → 404 after delete")

        print("== Error path ==")
        with mock.patch("core.audio.extract_audio",
                        side_effect=RuntimeError("boom: no audio")):
            up2 = client.post(
                "/api/upload",
                files={"file": ("broken.mp4", io.BytesIO(payload), "video/mp4")},
                data={"model_size": "small"},
            )
            job2 = up2.json()["job_id"]
            status2 = wait_terminal(client, job2)
        check(status2["stage"] == "error", "broken media → stage=error")
        check("extracting" in (status2["error"] or ""), "error names the stage")
        check("boom" in (status2["error"] or ""), "error carries the message")
        media2 = manager.get(job2).media_path
        if media2 and Path(media2).exists():
            Path(media2).unlink()
        check(client.post(f"/api/job/{job2}/retry").status_code == 410,
              "retry without source media → 410")
        client.delete(f"/api/job/{job2}")

    print("== Desktop shim (queue-based processor) ==")
    from app.processor import Processor, default_options
    from app.i18n import tr

    progresses, stages, item_kinds, ends = [], [], [], []
    fake_video = ROOT / "tests" / "_fake_video.mp4"
    fake_video.parent.mkdir(exist_ok=True)
    fake_video.write_bytes(payload)
    proc = Processor()
    try:
        with stubbed_pipeline():
            started = proc.start(
                [str(fake_video)],
                default_options(engine="google"),
                order="given",
            )
            check(started, "start() accepted (queue API)")
            check(proc.is_running, "worker runs on a background thread")

            deadline = time.time() + 30
            while time.time() < deadline and not ends:
                for ev in proc.drain():
                    kind = ev.get("type")
                    if kind == "progress":
                        progresses.append(ev["percent"])
                        stages.append(getattr(ev["stage"], "value", ev["stage"]))
                    elif kind == "item":
                        item_kinds.append(ev["event"].kind)
                    elif kind == "batch_end":
                        ends.append(ev)
                    elif kind == "fatal":
                        raise AssertionError(ev.get("error"))
                time.sleep(0.03)
            check(ends, "batch_end event delivered through the queue")

        # No cross-thread widget work: the processor only queues structured
        # events, and the GUI renders stage names in the *active language*.
        check("extracting" in stages and "translating" in stages,
              "stage enums stream through the queue")
        check(item_kinds == ["item_start", "item_done"],
              "item events report start → done")
        check(ends and str(fake_video) in ends[0]["done"] and not ends[0]["failed"],
              "batch_end reports the file as done")
        check(progresses and max(progresses) == 100.0, "progress reaches 100%")

        # Bilingual rendering now lives in i18n (the GUI paints it).
        check("استخراج الصوت" in tr("ar", "stage.extracting"),
              "Arabic status message preserved")
        check("تحويل الكلام إلى نص" in tr("ar", "stage.transcribing"),
              "transcribe status message preserved")
        check("✅" in tr("ar", "job.done"), "completion message preserved")
        check(tr("en", "stage.transcribing") != tr("ar", "stage.transcribing"),
              "English mirror differs from Arabic")
    finally:
        fake_video.unlink(missing_ok=True)
        for leftover in (ROOT / "tests").glob("_fake_video.*"):
            leftover.unlink()
        out_dir = ROOT / "tests" / "_out"
        if out_dir.exists():
            for leftover in out_dir.glob("*"):
                leftover.unlink()
            out_dir.rmdir()

    print("\nALL SMOKE TESTS PASSED ✔")


if __name__ == "__main__":
    main()
