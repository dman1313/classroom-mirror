"""Background camera loop. Frames stay in RAM and are dropped each tick."""

from __future__ import annotations

import threading
import time

from .engine import Detection, SessionEngine
from .identity import vector_from_gray
from .vision import crop_gray, detect_faces_bgr


class CaptureLoop:
    def __init__(self, engine: SessionEngine, camera_index: int):
        self.engine = engine
        self.camera_index = camera_index
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error: str | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="cm-v2-capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _run(self) -> None:
        import cv2

        cap = cv2.VideoCapture(self.camera_index)
        try:
            if not cap.isOpened():
                self.error = f"Camera {self.camera_index} could not be opened."
                return
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    self.error = f"Camera {self.camera_index} stopped sending frames."
                    break
                detections: list[Detection] = []
                for hit in detect_faces_bgr(frame):
                    gray = crop_gray(frame, hit)
                    if gray is None:
                        continue
                    h, w = frame.shape[:2]
                    bbox = (hit.x / w, hit.y / h, hit.w / w, hit.h / h)
                    detections.append(
                        Detection(bbox=bbox, vector=vector_from_gray(gray), person=None)
                    )
                self.engine.ingest(time.monotonic(), detections)
                del frame
                time.sleep(0.05)
        finally:
            cap.release()
