import os
import traceback
from app.audio_extractor import extract_audio
from app.transcriber import transcribe
from app.translator import translate_batch
from app.subtitle_writer import write_srt


class Processor:

    def __init__(self):
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def process(
        self,
        video_paths,
        output_dir,
        model_size,
        progress_callback=None,
        status_callback=None,
        item_callback=None,
    ):
        self._cancel = False
        total = len(video_paths)

        for idx, video_path in enumerate(video_paths):
            if self._cancel:
                if item_callback:
                    item_callback(video_path, "cancelled")
                break

            video_name = os.path.splitext(os.path.basename(video_path))[0]
            success = False

            # --- Step 1: Extract audio ---
            if status_callback:
                status_callback(
                    f"[{idx + 1}/{total}] استخراج الصوت من {video_name}..."
                )
            try:
                audio_path = extract_audio(video_path, output_dir)
            except Exception as e:
                if status_callback:
                    status_callback(f"❌ فشل استخراج الصوت من {video_name}: {e}")
                    status_callback(traceback.format_exc())
                if item_callback:
                    item_callback(video_path, "error")
                continue

            # --- Step 2: Transcribe ---
            if status_callback:
                status_callback(
                    f"[{idx + 1}/{total}] تحويل الكلام إلى نص..."
                )
            try:
                segments = transcribe(audio_path, model_size)
            except Exception as e:
                if status_callback:
                    status_callback(f"❌ فشل التعرف على الكلام: {e}")
                    status_callback(traceback.format_exc())
                self._cleanup(audio_path)
                if item_callback:
                    item_callback(video_path, "error")
                continue

            # --- Step 3: Translate ---
            if status_callback:
                status_callback(
                    f"[{idx + 1}/{total}] ترجمة النص إلى العربية..."
                )
            try:
                texts = [seg['text'].strip() for seg in segments]
                translated = translate_batch(texts)
            except Exception as e:
                if status_callback:
                    status_callback(f"❌ فشلت الترجمة: {e}")
                    status_callback(traceback.format_exc())
                self._cleanup(audio_path)
                if item_callback:
                    item_callback(video_path, "error")
                continue

            # --- Step 4: Write SRT ---
            try:
                srt_path = os.path.join(output_dir, f"{video_name}.srt")
                write_srt(segments, translated, srt_path)
                success = True
            except Exception as e:
                if status_callback:
                    status_callback(f"❌ فشلت كتابة ملف الترجمة: {e}")
                    status_callback(traceback.format_exc())
                self._cleanup(audio_path)
                if item_callback:
                    item_callback(video_path, "error")
                continue

            self._cleanup(audio_path)

            if status_callback:
                status_callback(f"✓ {video_name}.srt")

            if progress_callback:
                progress_callback((idx + 1) / total * 100)

            if item_callback:
                item_callback(video_path, "done")

        if status_callback:
            if self._cancel:
                status_callback("❌ تم الإيقاف")
            else:
                status_callback("✅ اكتملت الترجمة!")

    @staticmethod
    def _cleanup(path):
        try:
            os.remove(path)
        except Exception:
            pass
