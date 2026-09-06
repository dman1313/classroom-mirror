"""Background camera loop. Frames stay in RAM and are dropped each tick."""

from __future__ import annotations

import threading
import time

from .engine import Detection, SessionEngine
from .identity import vector_from_gray
from .motion import MotionTracker
from .vision import crop_gray, detect_faces_bgr, draw_motion_boxes, draw_overlay_boxes


class CaptureLoop:
    def __init__(self, engine: SessionEngine, camera_index: int):
        self.engine = engine
        self.camera_index = camera_index
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error: str | None = None
        # Frame-difference motion is the reliable "green = moving" signal at
        # classroom distance; it holds only the previous grayscale frame in RAM.
        self._motion = MotionTracker()
        # Number of regions currently moving, for the teacher's live count.
        self.motion_count = 0
        # Latest frame, JPEG-encoded in RAM for the teacher-only preview.
        # Never written to disk; replaced each tick and cleared on stop.
        self._frame_lock = threading.Lock()
        self._latest_jpeg: bytes | None = None

    def latest_jpeg(self) -> bytes | None:
        """Return the most recent frame as in-memory JPEG bytes (or None)."""
        with self._frame_lock:
            return self._latest_jpeg

    def _annotate(self, frame, motion_boxes):
        """Return a copy of ``frame`` with movement overlays drawn.

        Draws frame-difference motion regions (the primary green movement
        signal) plus any per-person numbered boxes the engine supplies. Always
        returns a drawable frame so the preview keeps showing live video even
        when no face is detected.
        """
        annotated = frame.copy()
        if motion_boxes:
            draw_motion_boxes(annotated, motion_boxes)
        overlay = getattr(self.engine, "overlay_boxes", None)
        boxes = overlay() if callable(overlay) else None
        if boxes:
            show_numbers = not getattr(self.engine, "hidden", False)
            draw_overlay_boxes(annotated, boxes, show_numbers=show_numbers)
        return annotated

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
        self._motion.reset()
        self.motion_count = 0

    _MAC_CAMERA_HINT = (
        " On macOS, allow camera access in System Settings > Privacy & Security "
        "> Camera (enable Terminal), then quit and reopen Terminal and Start "
        "again. Also close FaceTime, Zoom, or any app already using the camera."
    )

    def _run(self) -> None:
        import cv2

        try:
            cap = cv2.VideoCapture(self.camera_index)
        except Exception:
            self.error = (
                f"Camera {self.camera_index} could not be opened."
                + self._MAC_CAMERA_HINT
            )
            return
        try:
            if not cap.isOpened():
                self.error = (
                    f"Camera {self.camera_index} could not be opened."
                    + self._MAC_CAMERA_HINT
                )
                return
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    self.error = (
                        f"Camera {self.camera_index} stopped sending frames."
                        + self._MAC_CAMERA_HINT
                    )
                    break
                # Camera recovered after a transient read error.
                self.error = None
                motion_boxes = self._motion.detect(frame)
                self.motion_count = len(motion_boxes)
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
                self._publish_frame(self._annotate(frame, motion_boxes))
                del frame
                time.sleep(0.05)
        finally:
            cap.release()
