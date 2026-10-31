"""Video2ArabicSubs entry point.

    python main.py                 # desktop UI (Tkinter)
    python main.py --lang en       # force a UI language (ar | en)
    python main.py --web           # web app (FastAPI) on 127.0.0.1:7676
    python main.py --web --port 80 --host 0.0.0.0

Kept dependency-free on purpose: the Linux launcher installs the Python deps
into a per-user venv *before* this file is executed, and the Windows build
bundles them — so this only needs to pick a mode and start it.
"""
from __future__ import annotations

import argparse
import os
import sys

# Ensure the project root is on sys.path (works from any CWD).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="v2as",
        description="Video2ArabicSubs — فيديو ← ترجمة عربية (Arabic subtitles from any video)",
    )
    parser.add_argument("--web", action="store_true",
                        help="run the web app instead of the desktop UI")
    parser.add_argument("--host", default="127.0.0.1", help="web bind address")
    parser.add_argument("--port", type=int, default=7676, help="web port")
    parser.add_argument("--lang", choices=("ar", "en"), default=None,
                        help="interface language (default: ar)")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    return parser


def run_web(host: str, port: int) -> int:
    try:
        import uvicorn
    except ImportError:
        print("❌ Missing web dependencies.\n"
             "   pip install -r requirements.txt\n"
             "   (or on Debian: the first run of `v2as` installs them automatically)")
        return 1
    print(f"🌐 Video2ArabicSubs web app → http://{host}:{port}")
    uvicorn.run("web.main:app", host=host, port=port, log_level="info")
    return 0


def run_desktop(lang: str | None) -> int:
    try:
        from app.gui import App
    except ImportError as exc:
        print(f"❌ تعذّر تشغيل الواجهة: {exc}\n"
              f"   Could not start the desktop UI: {exc}\n\n"
              "   Linux: تأكد من تثبيت python3-tk و python3-venv ثم شغّل الحزمة مرة أخرى\n"
              "         (make sure python3-tk / python3-venv are installed)\n"
              "   Windows/any:  pip install -r requirements.txt")
        return 1
    App(lang=lang).run()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.version:
        from app import __version__
        print(__version__)
        return 0
    if args.web:
        return run_web(args.host, args.port)
    return run_desktop(args.lang)


if __name__ == "__main__":
    sys.exit(main())
