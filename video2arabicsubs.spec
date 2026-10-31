# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — Video2ArabicSubs desktop app (Windows).
#
#   pip install -r requirements-build.txt
#   pyinstaller --clean video2arabicsubs.spec
#
# Built as ONEDIR (dist/Video2ArabicSubs/…): the app bundles torch/whisper,
# so a onefile build would unpack gigabytes on every start. The NSIS
# installer (installer.nsi) packages that folder.

block_cipher = None

datas = [
    ("img", "img"),
    ("requirements.txt", "."),
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # runtime deps
        "whisper",
        "deep_translator",
        "moviepy",
        "imageio_ffmpeg",
        "pysrt",
        "pystray",
        "PIL",
        "PIL._tkinter_finder",
        "argostranslate",
        # application (modular, one macro per file)
        "app",
        "app.gui",
        "app.processor",
        "app.widgets",
        "app.theme",
        "app.i18n",
        "core",
        "core.pipeline",
        "core.batch",
        "core.credit",
        "core.models",
        "core.subtitles",
        "core.audio",
        "core.transcribe",
        "core.translate",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # web UI is not part of the desktop executable (v2as --web tells the
        # user to use the source/apt install instead)
        "uvicorn",
        "fastapi",
        "starlette",
        "web",
        "multipart",
        # build tooling
        "pytest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Video2ArabicSubs",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="img/first-logo-design.png",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Video2ArabicSubs",
)
