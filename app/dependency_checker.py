import importlib
import subprocess
import sys

REQUIRED = [
    "whisper",
    "deep_translator",
    "moviepy",
    "imageio_ffmpeg",
    "pysrt",
]


def missing_packages():
    missing = []
    for module in REQUIRED:
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(module)
    return missing


def auto_install(packages):
    if not packages:
        return True
    print("=" * 60)
    print(f"تثبيت المكتبات المطلوبة: {', '.join(packages)}")
    print("=" * 60)
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", *packages],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print("تم تثبيت جميع المكتبات بنجاح!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"فشل تثبيت المكتبات: {e}")
        return False


def check_and_install():
    missing = missing_packages()
    if missing:
        return auto_install(missing)
    return True
