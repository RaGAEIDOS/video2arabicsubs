"""M11 — unit tests for the v0.4 feature macros (no ML, no network).

Run:  python tests/features_test.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import batch, credit, subtitles                          # noqa: E402
from core.models import Cue, DEFAULT_ENGINE, ENGINES, JobOptions   # noqa: E402

PASS = 0
FAIL = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✔ {label}")
    else:
        FAIL += 1
        print(f"  ✘ {label}  {detail}")


def test_options_defaults() -> None:
    print("\n[M1] JobOptions defaults")
    opts = JobOptions()
    check("local engine is the default", opts.engine == DEFAULT_ENGINE == "argos")
    check("local engine comes first in ENGINES", ENGINES[0] == "argos")
    check("save next to video is ON", opts.save_next_to_video is True)
    check("credit is ON", opts.add_credit is True)
    d = opts.to_dict()
    check("to_dict exposes add_credit", d.get("add_credit") is True)
    check("to_dict exposes save_next_to_video", d.get("save_next_to_video") is True)
    check("google still accepted", JobOptions(engine="google").engine == "google")
    check("none still accepted", JobOptions(engine="none").engine == "none")


def test_credit() -> None:
    print("\n[M1] credit.py — visible final cue")
    check("credit text is exact",
          credit.CREDIT_TEXT == "تم الترجمة بواسطة https://github.com/RaGAEIDOS/video2arabicsubs")
    cues = [Cue(1, 0.0, 2.0, "مرحبا"), Cue(2, 2.0, 98.0, "مع السلامة")]
    out = credit.apply_credit(cues, duration=100.0)
    check("one cue appended", len(out) == len(cues) + 1)
    check("credit is the last cue", out[-1].text == credit.CREDIT_TEXT)
    check("aligned to video end", abs(out[-1].end - 100.0) < 1e-6, f"end={out[-1].end}")
    check("no overlap", out[-1].start >= out[-2].end - 1e-6)
    check("hold within 0.5..4s (truncated to free space)",
          0.5 <= out[-1].end - out[-1].start <= 4.5,
          f"span={out[-1].end - out[-1].start}")
    check("indices contiguous", [c.index for c in out] == list(range(1, len(out) + 1)))
    # No overlap with the previous cue
    check("no overlap", out[-1].start >= out[-2].end - 1e-9)
    # Toggle off
    check("disabled → unchanged", credit.apply_credit(cues, 100.0, enabled=False) == cues)
    # Empty list untouched
    check("empty list untouched", credit.apply_credit([], 100.0) == [])
    # No duration → just after the last cue
    out2 = credit.apply_credit(cues, duration=None)
    check("no duration → after last cue", abs(out2[-1].start - 98.25) < 1e-6)
    # Credit survives serialization round-trip
    text = subtitles.serialize(out, "srt")
    check("appears in SRT", credit.CREDIT_TEXT in text)
    text_vtt = subtitles.serialize(out, "vtt")
    check("appears in VTT", credit.CREDIT_TEXT in text_vtt)
    parsed = subtitles.parse(text)
    check("round-trip parse keeps it", parsed[-1].text == credit.CREDIT_TEXT)


def test_natural_order() -> None:
    print("\n[M3] batch — natural path ordering")
    check("ep2 before ep10",
          batch.sort_paths(["/a/ep10.mp4", "/a/ep2.mp4"]) == ["/a/ep2.mp4", "/a/ep10.mp4"])
    check("EP1 before ep2 (casefold)",
          batch.sort_paths(["/a/ep2.mp4", "/a/EP1.mp4"])[0].endswith("EP1.mp4"))
    check("path2/path10 across folders",
          batch.sort_paths(["/p10/v.mp4", "/p2/v.mp4"])[0] == "/p2/v.mp4")
    check("single digit groups", batch.sort_paths(["v1.mp4", "v10.mp4", "v9.mp4"])[0].endswith("v1.mp4"))


def test_scan() -> None:
    print("\n[M3] batch — folder scan")
    with tempfile.TemporaryDirectory() as tmp:
        names = ["ep10.mp4", "ep2.mp4", "notes.txt", "clip.MKV"]
        for n in names:
            (Path(tmp) / n).write_bytes(b"x")
        got = batch.scan_video_files(tmp)
        base = [os.path.basename(p) for p in got]
        check("only videos collected", base == ["clip.MKV", "ep2.mp4", "ep10.mp4"], str(base))
        check("is_video ext case-insensitive", batch.is_video("A.Mp4") and not batch.is_video("A.txt"))
        # recursive
        sub = Path(tmp) / "sub"
        sub.mkdir()
        (sub / "ep1.mp4").write_bytes(b"x")
        rec = [os.path.basename(p) for p in batch.scan_video_files(tmp, recursive=True)]
        check("recursive picks subfolder", "ep1.mp4" in rec, str(rec))
        # order kept: ep2 before ep10 even when recursive
        ordered = batch.sort_paths(batch.scan_video_files(tmp, recursive=True))
        idx = {os.path.basename(p): i for i, p in enumerate(ordered)}
        check("recursive order natural", idx["ep2.mp4"] < idx["ep10.mp4"], str(idx))


def test_run_batch() -> None:
    print("\n[M3] batch — sequential run with per-item events")
    from core.models import ProgressEvent, Stage, StageError

    calls = []

    def fake_run(media_path, output_dir, options, **kw):
        calls.append(os.path.basename(media_path))
        # progress events must be remapped into the batch's slice
        ev = kw.get("on_event")
        if ev:
            ev(ProgressEvent(stage=Stage.EXTRACTING, percent=50.0, stage_percent=0.5,
                             message="halfway"))
        if "bad" in media_path:
            raise StageError(Stage.TRANSCRIBING, "boom")
        class R:
            files = {"srt": media_path + ".srt"}
            language = "en"
            cues = [Cue(1, 0, 1, "x")]
        return R()

    import core.batch as batch_mod
    real = batch_mod.run_pipeline
    batch_mod.run_pipeline = fake_run
    try:
        items = []
        # Give an unsorted list; run_batch with order="path" must reorder.
        paths = ["/v/ep10.mp4", "/v/ep2.mp4", "/v/bad.mp4"]
        percents = []

        def on_item(ev):
            items.append(ev)

        def on_event(evt):
            percents.append(evt.percent)

        res = batch_mod.run_batch(
            paths, JobOptions(), output_dir=None, order="path",
            on_item=on_item, on_event=on_event,
        )
        # natural path order: bad < ep2 < ep10 (b sorts before e)
        check("processed in natural order", calls == ["bad.mp4", "ep2.mp4", "ep10.mp4"], str(calls))
        check("failing file recorded, batch continued",
              len(res.failed) == 1 and len(res.done) == 2, f"{res.failed} {res.done}")
        kinds = [i.kind for i in items]
        check("item_start/item_done/item_error events",
              kinds == ["item_start", "item_error", "item_start", "item_done",
                        "item_start", "item_done"], str(kinds))
        check("progress spans 0..100", percents and min(percents) >= 0 and max(percents) <= 100,
              f"{percents[:3]}…{percents[-3:] if percents else ''}")
        check("monotonic progress", all(b >= a for a, b in zip(percents, percents[1:])),
              str(percents[:10]))

        # order="given" keeps the user's ▲▼ arrangement
        calls.clear()
        batch_mod.run_batch(["/v/ep10.mp4", "/v/ep2.mp4"], JobOptions(),
                            order="given", on_item=lambda e: None, on_event=None)
        check("order='given' respects user order", calls == ["ep10.mp4", "ep2.mp4"], str(calls))

        # cancellation between files
        calls.clear()
        cancel = threading.Event()
        cancel.set()
        res2 = batch_mod.run_batch(["/v/a.mp4", "/v/b.mp4"], JobOptions(),
                                   cancel_event=cancel, on_item=lambda e: None)
        check("pre-cancelled batch runs nothing", calls == [] and res2.cancelled, str(calls))
    finally:
        batch_mod.run_pipeline = real


def main() -> int:
    test_options_defaults()
    test_credit()
    test_natural_order()
    test_scan()
    test_run_batch()
    print(f"\n{'=' * 50}\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
