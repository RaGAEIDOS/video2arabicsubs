# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

datas = [
    ("img", "img"),
    ("screenshots", "screenshots"),
    ("README.md", "."),
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "whisper",
        "deep_translator",
        "moviepy",
        "imageio_ffmpeg",
        "pysrt",
        "pystray",
        "PIL",
        "PIL._tkinter_finder",
        "app",
        "app.gui",
        "app.processor",
        "app.audio_extractor",
        "app.transcriber",
        "app.translator",
        "app.subtitle_writer",
        "app.dependency_checker",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Video2ArabicSubs",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="img/first-logo-design.png",
)
