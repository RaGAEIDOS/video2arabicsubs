"""Compatibility orchestrator for the Tkinter GUI.

The GUI keeps calling ``Processor.process(...)`` with the exact same
callbacks and Arabic status strings as before — but the actual work now
runs through the shared, GUI-free engine in ``core/``.
"""
import os
import threading
import traceback

from core.models import JobOptions, PipelineCancelled, Stage, StageError
from core.pipeline import run_pipeline

# Stage → Arabic status lines used by the original GUI (None = stay silent).
_STAGE_MESSAGES = {
    Stage.EXTRACTING: "استخراج الصوت من {name}...",
    Stage.TRANSCRIBING: "تحويل الكلام إلى نص...",
    Stage.TRANSLATING: "ترجمة النص إلى العربية...",
    Stage.GENERATING: None,
    Stage.BURNING: "حرق الترجمة في الفيديو...",
}

_FAILURE_MESSAGES = {
    Stage.EXTRACTING: "❌ فشل استخراج الصوت من {name}: {error}",
    Stage.TRANSCRIBING: "❌ فشل التعرف على الكلام: {error}",
    Stage.TRANSLATING: "❌ فشلت الترجمة: {error}",
    Stage.GENERATING: "❌ فشلت كتابة ملف الترجمة: {error}",
    Stage.BURNING: "❌ فشلت عملية حرق الترجمة: {error}",
}


class Processor:

    def __init__(self):
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def process(
        self,
        video_paths,
        output_dir,
        model_size,
        progress_callback=None,
        status_callback=None,
        item_callback=None,
    ):
        self._cancel.clear()
        total = len(video_paths)
        options = JobOptions(
            model_size=model_size,
            source_language="en",
            engine="google",
            output_format="srt",
        )

        for idx, video_path in enumerate(video_paths):
            if self._cancel.is_set():
                if item_callback:
                    item_callback(video_path, "cancelled")
                break

            video_name = os.path.splitext(os.path.basename(video_path))[0]

            def on_event(event, _idx=idx, _total=total, _name=video_name, _state={"last": None}):
                template = _STAGE_MESSAGES.get(event.stage, None)
                if event.stage != _state["last"]:
                    _state["last"] = event.stage
                    if template and status_callback:
                        status_callback(
                            f"[{_idx + 1}/{_total}] {template.format(name=_name)}"
                        )
                if progress_callback:
                    progress_callback(event.percent)

            try:
                run_pipeline(
                    video_path,
                    output_dir,
                    options,
                    base_name=video_name,
                    on_event=on_event,
                    cancel_event=self._cancel,
                    progress_offset=idx * 100.0 / total,
                    progress_scale=100.0 / total,
                )
            except PipelineCancelled:
                if item_callback:
                    item_callback(video_path, "cancelled")
                break
            except StageError as exc:
                if status_callback:
                    template = _FAILURE_MESSAGES.get(
                        exc.stage, "❌ فشلت المعالجة: {error}"
                    )
                    status_callback(
                        template.format(name=video_name, error=exc.message)
                    )
                    status_callback(exc.traceback_text())
                if item_callback:
                    item_callback(video_path, "error")
                continue

            if status_callback:
                status_callback(f"✓ {video_name}.srt")
            if progress_callback:
                progress_callback((idx + 1) / total * 100)
            if item_callback:
                item_callback(video_path, "done")

        if status_callback:
            if self._cancel.is_set():
                status_callback("❌ تم الإيقاف")
            else:
                status_callback("✅ اكتملت الترجمة!")
