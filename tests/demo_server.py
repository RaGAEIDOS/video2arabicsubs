"""Run the web app with the ML stages stubbed — for frontend work & demos.

Lets you exercise the full UI (upload → live progress → editor →
downloads → burned video) in a browser without whisper/torch/moviepy
installed and without network access.

    python tests/demo_server.py          # http://127.0.0.1:8477
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAKE_SEGMENTS = [
    {"start": 0.0, "end": 2.4, "text": " Hello everyone and welcome back."},
    {"start": 2.4, "end": 5.1, "text": " Today we will learn something new."},
    {"start": 5.1, "end": 8.8, "text": " Thank you for watching."},
    {"start": 8.8, "end": 12.5, "text": " Do not forget to subscribe."},
    {"start": 12.5, "end": 16.0, "text": " See you in the next video."},
]
FAKE_ARABIC = [
    "مرحباً بكم جميعاً وعوداً موفقة",
    "اليوم سوف نتعلم شيئاً جديداً",
    "شكراً لمشاهدتكم",
    "لا تنسوا الاشتراك في القناة",
    "أراكم في الفيديو القادم",
]


def fake_extract(video_path, output_dir=None, cancel_event=None):
    time.sleep(0.6)
    wav = os.path.join(output_dir, "demo.wav")
    with open(wav, "wb") as fh:
        fh.write(b"RIFF0000WAVEfmt ")
    return wav


def fake_transcribe(audio_path, model_size="small", language="en",
                    on_progress=None, cancel_event=None):
    steps = 30
    for i in range(steps):
        if cancel_event is not None and cancel_event.is_set():
            from core.models import PipelineCancelled
            raise PipelineCancelled()
        time.sleep(0.12)
        if on_progress:
            on_progress((i + 1) / steps)
    return {"segments": [dict(s) for s in FAKE_SEGMENTS], "language": "en"}


def fake_translate(texts, source="en", target="ar", engine="google",
                   on_progress=None, cancel_event=None, **_kw):
    out = list(texts)
    for i, text in enumerate(texts):
        if text.strip() and i < len(FAKE_ARABIC):
            out[i] = FAKE_ARABIC[i]
        time.sleep(0.15)
        if on_progress:
            on_progress((i + 1) / max(1, len(texts)))
        if cancel_event is not None and cancel_event.is_set():
            from core.models import PipelineCancelled
            raise PipelineCancelled()
    if on_progress:
        on_progress(1.0)
    return out


def main() -> None:
    port = int(os.environ.get("PORT", "8477"))
    patches = [
        mock.patch("core.audio.extract_audio", side_effect=fake_extract),
        mock.patch("core.audio.probe_duration", return_value=16.0),
        mock.patch("core.transcribe.transcribe", side_effect=fake_transcribe),
        mock.patch("core.translate.translate_batch", side_effect=fake_translate),
    ]
    for patch in patches:
        patch.start()

    import uvicorn

    from web.main import app

    print(f"▶ Demo server (stubbed ML): http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
