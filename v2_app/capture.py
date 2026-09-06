"""Background camera loop. Frames stay in RAM and are dropped each tick."""

from __future__ import annotations

import threading
import time

from .engine import Detection, SessionEngine
from .identity import vector_from_gray
from .vision import crop_gray, detect_faces_bgr, draw_overlay_boxes


class CaptureLoop:
    def __init__(self, engine: SessionEngine, camera_index: int):
        self.engine = engine
        self.camera_index = camera_index
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error: str | None = None
        # Latest frame, JPEG-encoded in RAM for the teacher-only preview.
        # Never written to disk; replaced each tick and cleared on stop.
        self._frame_lock = threading.Lock()
        self._latest_jpeg: bytes | None = None

    def latest_jpeg(self) -> bytes | None:
        """Return the most recent frame as in-memory JPEG bytes (or None)."""
        with self._frame_lock:
            return self._latest_jpeg

    def _annotate(self, frame):
        """Return a copy of ``frame`` with movement overlays drawn.

        Falls back to the original frame if the engine cannot supply boxes
        (e.g. a stub engine in tests), so the preview always shows video.
        """
        overlay = getattr(self.engine, "overlay_boxes", None)
        if not callable(overlay):
            return frame
        boxes = overlay()
        if not boxes:
            return frame
        annotated = frame.copy()
        show_numbers = not getattr(self.engine, "hidden", False)
        return draw_overlay_boxes(annotated, boxes, show_numbers=show_numbers)

    def _publish_frame(self, frame) -> None:
        import cv2

        # imencode returns the JPEG in a RAM buffer; it does not touch disk.
        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            return
        data = buf.tobytes()
        with self._frame_lock:
            self._latest_jpeg = data

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="cm-v2-capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        with self._frame_lock:
            self._latest_jpeg = None

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
                # Annotate a throwaway copy so movement is visible in the
                # teacher preview. The annotated frame is never stored.
                self._publish_frame(self._annotate(frame))
                del frame
                time.sleep(0.05)
        finally:
            cap.release()
