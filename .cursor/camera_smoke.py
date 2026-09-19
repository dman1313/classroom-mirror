#!/usr/bin/env python3
"""Headless end-to-end smoke of the REAL pose pipeline, no webcam required.

The Cloud Agent VM has no camera and cannot create one (no kernel modules, so
no v4l2loopback). But OpenCV here is built with the FFMPEG backend, so
`cv2.VideoCapture(<file>)` works. The app already exposes that seam via
`app.camera.VideoFileSource` / `process_video`, so we can push a generated
video file through the actual YOLO pose model and a real engine end to end.

This exercises: model load -> per-frame inference -> engine aggregation ->
finish rows. Detection *counts* depend on how realistic the input is (abstract
shapes are usually not detected as people); detection *quality* is covered
separately by the synthetic-keypoint fixtures, which bypass the model on
purpose. The goal here is to prove the real pipeline runs unattended.

Usage (from the repo root):
    ./.venv/bin/python .cursor/camera_smoke.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np

from app.camera import process_video
from app.detector import PoseDetector
from app.session import Mode2Engine


def _make_synthetic_video(path: str, *, seconds: float = 2.0, fps: int = 10,
                          size: tuple[int, int] = (320, 240)) -> int:
    w, h = size
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not writer.isOpened():
        raise RuntimeError("OpenCV could not open an mp4 VideoWriter (FFMPEG backend).")
    frames = int(seconds * fps)
    for i in range(frames):
        frame = np.full((h, w, 3), 30, dtype=np.uint8)
        # a moving blob so successive frames differ (motion for the tracker)
        cx = int(w * (0.2 + 0.6 * i / max(frames - 1, 1)))
        cv2.rectangle(frame, (cx - 25, h // 2 - 55), (cx + 25, h // 2 + 55), (200, 200, 200), -1)
        cv2.circle(frame, (cx, h // 2 - 70), 18, (200, 200, 200), -1)
        writer.write(frame)
    writer.release()
    return frames


def main() -> int:
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    try:
        n = _make_synthetic_video(tmp.name)
        print(f"Generated synthetic video: {n} frames -> {tmp.name}")

        detector = PoseDetector()  # loads the real yolo11n-pose model
        rows = process_video(tmp.name, detector, Mode2Engine())

        print("Pipeline ran end to end through the real model (FFMPEG file backend).")
        print(f"Mode2 engine produced {len(rows)} minute row(s):")
        for minute, bodies, raises, bucket in rows:
            print(f"  minute={minute} bodies={bodies} raises={raises} movement={bucket}")
        print("PASS: headless real-model pipeline smoke completed.")
        return 0
    finally:
        os.unlink(tmp.name)


if __name__ == "__main__":
    raise SystemExit(main())
