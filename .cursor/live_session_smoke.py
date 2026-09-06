#!/usr/bin/env python3
"""Headless end-to-end smoke of the REAL V1 live-session lifecycle, no webcam.

This drives `app.camera.CameraService` exactly as the running app does — start
a session, run the capture -> detect -> engine loop (including the in-memory
MJPEG encode), stop, persist, and render the report — but feeds frames from a
generated video file instead of a physical camera.

The ONLY substitution is the frame *source*: `app.camera.WebcamSource` is
swapped (in this process only) for the repository's existing `VideoFileSource`
seam, which the code already provides "for tests and demos". No product code is
modified. Nothing is written except a temp video fixture and a temp SQLite DB,
both removed at the end; the smoke also asserts that no image/video/frame file
was written during the run (consistent with guardrail 1: frames stay in RAM).

Usage (from the repo root):
    ./.venv/bin/python .cursor/live_session_smoke.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np

import app.camera as camera_mod
from app.camera import VideoFileSource, persist_results  # noqa: F401  (seam + parity)
from app.db import Database
from app import reports


IMAGE_VIDEO_SUFFIXES = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp",
                        ".mp4", ".mov", ".avi", ".mkv", ".m4v")


def _make_synthetic_video(path: str, *, seconds: float = 3.0, fps: int = 10,
                          size: tuple[int, int] = (320, 240)) -> int:
    w, h = size
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not writer.isOpened():
        raise RuntimeError("OpenCV could not open an mp4 VideoWriter (FFMPEG backend).")
    frames = int(seconds * fps)
    for i in range(frames):
        frame = np.full((h, w, 3), 30, dtype=np.uint8)
        cx = int(w * (0.2 + 0.6 * i / max(frames - 1, 1)))
        cv2.rectangle(frame, (cx - 25, h // 2 - 55), (cx + 25, h // 2 + 55), (200, 200, 200), -1)
        cv2.circle(frame, (cx, h // 2 - 70), 18, (200, 200, 200), -1)
        writer.write(frame)
    writer.release()
    return frames


class _LoopingVideoSource:
    """A camera-shaped source that replays a video file so the session runs
    for a bounded number of reads instead of ending at the first EOF."""

    def __init__(self, path: str, max_reads: int):
        self._path = path
        self._max_reads = max_reads
        self._reads = 0
        self._src = VideoFileSource(path)

    def read(self):
        if self._reads >= self._max_reads:
            return None
        item = self._src.read()
        if item is None:
            self._src.release()
            self._src = VideoFileSource(self._path)
            item = self._src.read()
            if item is None:
                return None
        self._reads += 1
        return item

    def release(self):
        self._src.release()


def _no_media_files_under(root: str) -> bool:
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name.lower().endswith(IMAGE_VIDEO_SUFFIXES):
                print(f"  UNEXPECTED media file written: {os.path.join(dirpath, name)}")
                return False
    return True


def main() -> int:
    workdir = tempfile.mkdtemp(prefix="cm-live-smoke-")
    video_path = os.path.join(workdir, "fixture.mp4")
    data_dir = os.path.join(workdir, "data")

    original_webcam = camera_mod.WebcamSource
    try:
        n = _make_synthetic_video(video_path)
        print(f"Generated synthetic video: {n} frames -> {video_path}")

        # Swap ONLY the frame source (in this process). Everything downstream
        # — detector, engine, DB, reports — is the real code path.
        camera_mod.WebcamSource = lambda *a, **k: _LoopingVideoSource(video_path, max_reads=10_000)

        from app.detector import PoseDetector

        db = Database(data_dir=data_dir)
        camera = camera_mod.CameraService(lambda: PoseDetector())

        session_id = camera.start_session(db, mode="mode2", phase="none",
                                          class_code="6B", designations=[])
        print(f"Started live mode2 session {session_id}; capturing for ~3s...")
        time.sleep(3.0)
        stopped = camera.stop_session(db)
        camera.shutdown()
        print(f"Stopped session {stopped}.")

        rows = db.mode2_data(session_id)
        html = reports.mode2_summary_html(db, session_id)
        db.close()

        assert stopped == session_id, "stop_session did not return the started session"
        assert rows, "no mode2 minute rows were persisted from the live loop"
        assert "Whole-class session summary" in html, "report did not render"

        print(f"Persisted {len(rows)} mode2 minute row(s) from the live capture loop:")
        for r in rows:
            print(f"  minute={r['minute']} bodies={r['bodies_detected']} "
                  f"raises={r['hand_raises']} movement={r['movement_bucket']}")

        # Guardrail 1: the runtime must persist no frames. Scan the app's data
        # directory (where any runtime write would land), NOT the whole temp dir
        # — the latter also holds our input fixture video.
        assert _no_media_files_under(data_dir), \
            "the live run wrote an image/video file (guardrail 1 violation)"
        persisted = sorted(
            os.path.relpath(os.path.join(d, f), data_dir)
            for d, _s, fs in os.walk(data_dir) for f in fs
        )
        print(f"Runtime wrote only: {persisted} (frames stayed in RAM).")
        print("PASS: headless real live-session lifecycle smoke completed.")
        return 0
    finally:
        camera_mod.WebcamSource = original_webcam
        import shutil
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
