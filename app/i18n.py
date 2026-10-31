"""M5 macro — bilingual (Arabic / English) string table for the desktop UI.

Keeping every user-visible string in one isolated module means:

* the language toggle is a pure data lookup (no widget knows a language),
* adding a new language = adding one dict,
* RTL/LTR is decided from the active language, not hard-coded per widget.

Usage::

    from app.i18n import tr, LANGS
    tr("ar", "app.title")            # → "Video2ArabicSubs"
    tr("en", "source.pick_files")    # → "Choose videos"
    tr("ar", "job.video_count", n=3) # → "3 فيديو"
"""
from __future__ import annotations

from typing import Dict

#: Language codes offered in the UI, with their native display names.
LANGS: Dict[str, str] = {"ar": "العربية", "en": "English"}

#: Default language on first launch.
DEFAULT_LANG = "ar"

#: Right-to-left languages (drive the layout mirroring flag).
RTL_LANGS = frozenset({"ar", "fa", "ur", "he"})

STRINGS: Dict[str, Dict[str, str]] = {
    # ── Header / app ──────────────────────────────────────────────────
    "ar": {
        "app.tagline": "حوّل أي فيديو إلى ترجمة عربية بسهولة",
        "app.version": "الإصدار {version}",
        "app.github": "GitHub",
        "app.language": "اللغة",

        # ── Source card ───────────────────────────────────────────────
        "source.title": "مصدر الفيديو",
        "source.files": "📁 ملفات",
        "source.folder": "📂 مجلد بالترتيب",
        "source.pick_files": "اختر فيديوهات",
        "source.pick_folder": "اختر مجلداً",
        "source.recursive": "شمول المجلدات الفرعية",
        "source.order_hint": "تُعالَج بالترتيب الطبيعي للمسار ( ep2 قبل ep10 )",
        "source.empty": "لا توجد فيديوهات بعد — أضف ملفات أو اختر مجلداً.",
        "source.count": "{n} فيديو في القائمة",
        "source.up": "نقل لأعلى",
        "source.down": "نقل لأسفل",
        "source.remove": "إزالة",
        "source.clear": "مسح القائمة",
        "source.folder_loaded": "تم تحميل {n} فيديو من: {path}",

        # ── Options card ──────────────────────────────────────────────
        "opt.title": "خيارات المعالجة",
        "opt.model": "نموذج Whisper",
        "opt.engine": "الترجمة",
        "opt.engine_local": "عربي · محلي (بدون إنترنت)",
        "opt.engine_google": "عربي · جوجل (أونلاين)",
        "opt.engine_none": "إنجليزي · بدون ترجمة",
        "opt.format": "صيغة ملف الترجمة",
        "opt.fmt_srt": "SRT",
        "opt.fmt_vtt": "VTT",
        "opt.fmt_both": "SRT + VTT",
        "opt.where": "مكان حفظ ملف الترجمة",
        "opt.next_to_video": "بجانب الفيديو",
        "opt.custom_folder": "مجلد مخصص",
        "opt.custom_folder_btn": "اختيار…",
        "opt.toggles": "إضافات",
        "opt.credit": "إضافة سطر الترويج في النهاية",
        "opt.credit_hint": "«{text}» — يظهر ثوانٍ آخر الفيديو",
        "opt.burn": "حرق الترجمة داخل الفيديو (اختياري)",
        "opt.burn_hint": "يتطلب FFmpeg بدعم libass — يبطئ المعالجة قليلاً.",
        "opt.burn_unavailable": "الحرق غير متاح: FFmpeg بدون دعم libass",
        "opt.bom": "ترميز UTF-8 مع BOM (توافق مشغّلات ويندوز)",

        # ── Job card ──────────────────────────────────────────────────
        "job.title": "حالة المعالجة",
        "job.start": "▶ ابدأ الترجمة",
        "job.stop": "⏹ إيقاف",
        "job.idle": "جاهز للترجمة",
        "job.idle_sub": "اختر الفيديوهات واضبط الخيارات ثم اضغط «ابدأ الترجمة».",
        "job.running": "جارٍ الترجمة…",
        "job.done": "✅ اكتملت الترجمة بنجاح",
        "job.done_sub": "اكتمل {ok} من {total} فيديو.",
        "job.cancelled": "تم الإيقاف",
        "job.failed": "فشل: {name}",
        "job.current": "الآن: {name}",
        "job.progress_of": "الفيديو {i}/{n}",
        "job.files": "الملفات الناتجة:",
        "job.log": "سجل التشغيل",
        "job.log_clear": "مسح",
        "job.need_input": "يرجى إضافة فيديو واحد على الأقل.",
        "job.cues": "{n} سطر",

        # ── Pipeline stages ───────────────────────────────────────────
        "stage.queued": "في الانتظار",
        "stage.downloading": "تنزيل الفيديو",
        "stage.extracting": "استخراج الصوت",
        "stage.transcribing": "تحويل الكلام إلى نص",
        "stage.translating": "الترجمة إلى العربية",
        "stage.generating": "إنشاء ملف الترجمة",
        "stage.burning": "حرق الترجمة في الفيديو",
        "stage.done": "اكتمل",
        "stage.error": "فشل",
        "stage.cancelled": "أُلغيت",

        # ── File list statuses ────────────────────────────────────────
        "status.pending": "بانتظار",
        "status.active": "يعمل",
        "status.done": "تم",
        "status.error": "خطأ",
        "status.cancelled": "أُلغي",

        # ── Tray / misc ───────────────────────────────────────────────
        "tray.show": "إظهار النافذة",
        "tray.quit": "خروج",
        "dlg.error_title": "خطأ",
        "dlg.warn_title": "تحذير",
        "dlg.confirm_stop": "إيقاف المعالجة الحالية؟",
    },
    # ── English mirror ─────────────────────────────────────────────────
    "en": {
        "app.tagline": "Turn any video into Arabic subtitles in one click",
        "app.version": "v{version}",
        "app.github": "GitHub",
        "app.language": "Language",

        "source.title": "Video source",
        "source.files": "📁 Files",
        "source.folder": "📂 Folder (ordered)",
        "source.pick_files": "Choose videos",
        "source.pick_folder": "Choose folder",
        "source.recursive": "Include sub-folders",
        "source.order_hint": "Processed in natural path order (ep2 before ep10)",
        "source.empty": "No videos yet — add files or pick a folder.",
        "source.count": "{n} video(s) in the list",
        "source.up": "Move up",
        "source.down": "Move down",
        "source.remove": "Remove",
        "source.clear": "Clear list",
        "source.folder_loaded": "Loaded {n} video(s) from: {path}",

        "opt.title": "Processing options",
        "opt.model": "Whisper model",
        "opt.engine": "Translation",
        "opt.engine_local": "Arabic · local (offline)",
        "opt.engine_google": "Arabic · Google (online)",
        "opt.engine_none": "English · no translation",
        "opt.format": "Subtitle format",
        "opt.fmt_srt": "SRT",
        "opt.fmt_vtt": "VTT",
        "opt.fmt_both": "SRT + VTT",
        "opt.where": "Save subtitles to",
        "opt.next_to_video": "Next to the video",
        "opt.custom_folder": "Custom folder",
        "opt.custom_folder_btn": "Browse…",
        "opt.toggles": "Extras",
        "opt.credit": "Append the promo credit at the end",
        "opt.credit_hint": "“{text}” — shows for a few seconds at the end",
        "opt.burn": "Burn subtitles into the video (optional)",
        "opt.burn_hint": "Needs FFmpeg with libass — slightly slower.",
        "opt.burn_unavailable": "Burn-in unavailable: FFmpeg lacks libass",
        "opt.bom": "UTF-8 with BOM (Windows player friendly)",

        "job.title": "Processing status",
        "job.start": "▶ Start translating",
        "job.stop": "⏹ Stop",
        "job.idle": "Ready to translate",
        "job.idle_sub": "Add videos, adjust the options, then press “Start”.",
        "job.running": "Translating…",
        "job.done": "✅ Translation complete",
        "job.done_sub": "{ok} of {total} video(s) finished.",
        "job.cancelled": "Stopped",
        "job.failed": "Failed: {name}",
        "job.current": "Now: {name}",
        "job.progress_of": "Video {i}/{n}",
        "job.files": "Output files:",
        "job.log": "Log",
        "job.log_clear": "Clear",
        "job.need_input": "Please add at least one video.",
        "job.cues": "{n} cue(s)",

        "stage.queued": "Queued",
        "stage.downloading": "Downloading video",
        "stage.extracting": "Extracting audio",
        "stage.transcribing": "Transcribing speech",
        "stage.translating": "Translating to Arabic",
        "stage.generating": "Generating subtitles",
        "stage.burning": "Burning subtitles",
        "stage.done": "Done",
        "stage.error": "Failed",
        "stage.cancelled": "Cancelled",

        "status.pending": "Pending",
        "status.active": "Working",
        "status.done": "Done",
        "status.error": "Error",
        "status.cancelled": "Cancelled",

        "tray.show": "Show window",
        "tray.quit": "Quit",
        "dlg.error_title": "Error",
        "dlg.warn_title": "Warning",
        "dlg.confirm_stop": "Stop the current processing?",
    },
}


def tr(lang: str, key: str, **kwargs) -> str:
    """Translate ``key`` for ``lang``; falls back to English then to the key.

    ``**kwargs`` are formatted in (so ``tr("ar", "job.progress_of", i=1, n=3)``
    works). Missing keys never crash the UI — they degrade gracefully.
    """
    table = STRINGS.get(lang) or STRINGS[DEFAULT_LANG]
    text = table.get(key)
    if text is None:
        text = STRINGS["en"].get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            pass
    return text


def is_rtl(lang: str) -> bool:
    return lang in RTL_LANGS
