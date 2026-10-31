"""Capture modern screenshots of the desktop UI for the README (M14).

Runs against the real Tkinter app on the available display, fakes a small
in-progress batch so the UI shows life, and saves PNGs into screenshots/.

    python tests/screenshot.py            # writes screenshots/desktop-ar.png …
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DISPLAY", ":0")

OUT = ROOT / "screenshots"
OUT.mkdir(exist_ok=True)

SAMPLE = [
    "/home/meuor/Videos/EP01_intro.mp4",
    "/home/meuor/Videos/EP02_setup.mp4",
    "/home/meuor/Videos/EP03_workflow.mp4",
    "/home/meuor/Videos/EP10_advanced.mp4",
]


def grab(window, path):
    """Screenshot just the app window (crop the root capture to its bounds)."""
    window.update_idletasks()
    window.update()
    try:
        # Window position/size in screen coordinates (include WM frame).
        x = window.winfo_rootx()
        y = window.winfo_rooty()
        w = window.winfo_width()
        h = window.winfo_height()
        geom = f"{w}x{h}+{x}+{y}"
        subprocess.run(["import", "-window", "root", "-crop", geom,
                        "+repage", str(path)], check=True)
        print(f"  ✔ {path}  ({w}x{h} @ {x},{y})")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  ✘ {path}: {exc}")
        return False


def seed(app, stage, percent, log_lines, active_idx=2, done_upto=1):
    app.videos = list(SAMPLE)
    for p in app.videos:
        app.status[p] = "pending"
    for p in app.videos[:done_upto]:
        app.status[p] = "done"
    if active_idx < len(app.videos):
        app.status[app.videos[active_idx]] = "active"
    app.selected = active_idx
    app._render_rows()
    app._update_stepper(stage)
    app.progress.set(percent, active=True)
    app.lbl_percent.configure(text=f"{percent:.0f}%")
    app.lbl_current.configure(text=app._t("job.current", name=Path(app.videos[active_idx]).name))
    for line, tag in log_lines:
        app._log(line, tag)


def main():
    from app.gui import App

    app = App(lang="ar")
    app.root.update_idletasks(); app.root.update()
    app.root.after(700, lambda: None)
    # let entrance animations settle
    for _ in range(8):
        app.root.update()
        app.root.after(40)

    seed(
        app,
        stage="translating",
        percent=52,
        log_lines=[
            ("▶ [1/4] EP01_intro.mp4", "info"),
            ("✔ EP01_intro.mp4 — 148 سطر · EP01_intro.srt", "ok"),
            ("▶ [2/4] EP02_setup.mp4", "info"),
            ("✔ EP02_setup.mp4 — 96 سطر · EP02_setup.srt", "ok"),
            ("▶ [3/4] EP03_workflow.mp4", "info"),
        ],
        active_idx=2,
        done_upto=2,
    )
    for _ in range(10):
        app.root.update()
        app.root.after(40)

    grab(app.root, OUT / "desktop-ar.png")

    # English view
    app._set_lang("en")
    for _ in range(8):
        app.root.update()
        app.root.after(40)
    grab(app.root, OUT / "desktop-en.png")

    # Empty/idle view (fresh launch look)
    app2 = App(lang="en")
    app2.root.update_idletasks(); app2.root.update()
    for _ in range(10):
        app2.root.update()
        app2.root.after(40)
    grab(app2.root, OUT / "desktop-idle.png")

    print("done")


if __name__ == "__main__":
    main()
