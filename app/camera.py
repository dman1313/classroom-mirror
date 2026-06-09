"""Frame sources and the live camera service.

Frames exist in memory only: they go camera -> detector -> numbers, and the
preview is JPEG bytes streamed over localhost HTTP. Nothing here has a code
path that writes a frame to disk (guardrail 1).
"""
import threading
import time
from typing import Optional

import cv2

from .heuristics import KeypointFrame
from .session import Mode1Engine, Mode2Engine


class VideoFileSource:
    """Plays a video file as if it were a camera (tests and demos)."""

    def __init__(self, path: str):
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open video file: {path}")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        self.i = 0

    def read(self):
        ok, frame = self.cap.read()
        if not ok:
            return None
        t = self.i / self.fps
        self.i += 1
        return t, frame

    def release(self):
        self.cap.release()


class WebcamSource:
    def __init__(self, index: int = 0):
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            raise RuntimeError(
                "No camera found. Plug in or allow the camera (macOS will ask "
                "the first time), then try again."
            )
        self.t0 = time.monotonic()

    def read(self):
        ok, frame = self.cap.read()
        if not ok:
            return None
        return time.monotonic() - self.t0, frame

    def release(self):
        self.cap.release()


def process_video(path: str, detector, engine, detect_every: int = 3):
    """Run a whole video file through an engine, offline. Used by tests."""
    src = VideoFileSource(path)
    n = 0
    while True:
        item = src.read()
        if item is None:
            break
        t, frame = item
        if n % detect_every == 0:
            engine.update(KeypointFrame(t, detector.detect(frame)))
        n += 1
    src.release()
    return engine.finish()


def persist_results(db, session_id: int, mode: str, results):
    if mode == "mode1":
        minute_rows, event_rows = results
        for lims, minute, pct, bucket in minute_rows:
            db.add_mode1_minute(session_id, lims, minute, pct, bucket)
        for lims, t in event_rows:
            db.add_mode1_event(session_id, lims, t)
    else:
        for minute, bodies, raises, bucket in results:
            db.add_mode2_minute(session_id, minute, bodies, raises, bucket)
    db.end_session(session_id)


class CameraService:
    """One camera, two states: idle preview (no detection, nothing stored)
    and an active session (detection feeding an engine)."""

    def __init__(self, detector_factory):
        self._detector_factory = detector_factory
        self._detector = None
        self._source: Optional[WebcamSource] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._stop_flag = False
        self._latest_jpeg: Optional[bytes] = None
        self.engine = None
        self.session_id: Optional[int] = None
        self.mode: Optional[str] = None
        self.last_error: Optional[str] = None

    # -- lifecycle --------------------------------------------------------

    def ensure_running(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._source = WebcamSource()
            self._stop_flag = False
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def start_session(self, db, mode: str, phase: str, class_code: str, designations):
        with self._lock:
            if self.session_id is not None:
                raise RuntimeError("A session is already running — stop it first.")
        session_id = db.start_session(mode, phase, class_code, designations)
        if mode == "mode1":
            zones = {d["lims"]: tuple(d["zone"]) for d in designations}
            engine = Mode1Engine(zones)
        else:
            engine = Mode2Engine()
        self.ensure_running()
        with self._lock:
            self.engine = engine
            self.session_id = session_id
            self.mode = mode
            self._t0 = time.monotonic()
        return session_id

    def stop_session(self, db) -> Optional[int]:
        with self._lock:
            engine, session_id, mode = self.engine, self.session_id, self.mode
            self.engine = None
            self.session_id = None
            self.mode = None
        if engine is None or session_id is None:
            return None
        persist_results(db, session_id, mode, engine.finish())
        return session_id

    def shutdown(self):
        self._stop_flag = True
        if self._thread:
            self._thread.join(timeout=2)
        if self._source:
            self._source.release()

    # -- capture loop -----------------------------------------------------

    def _loop(self):
        n = 0
        while not self._stop_flag:
            item = self._source.read()
            if item is None:
                self.last_error = "The camera stopped sending pictures."
                break
            _, frame = item
            with self._lock:
                engine, t0 = self.engine, getattr(self, "_t0", None)
            persons = []
            if engine is not None and n % 3 == 0:
                if self._detector is None:
                    self._detector = self._detector_factory()
                t = time.monotonic() - t0
                persons = self._detector.detect(frame)
                engine.update(KeypointFrame(t, persons))
            self._annotate(frame, engine, persons)
            ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                self._latest_jpeg = jpg.tobytes()  # memory only
            n += 1
            time.sleep(0.01)

    def _annotate(self, frame, engine, persons):
        h, w = frame.shape[:2]
        for p in persons:
            cx, cy = p.centroid
            cv2.circle(frame, (int(cx * w), int(cy * h)), 6, (216, 176, 143), -1)
        if isinstance(engine, Mode1Engine):
            for lims, (zx, zy, zw, zh) in engine.zones.items():
                cv2.rectangle(frame, (int(zx * w), int(zy * h)),
                              (int((zx + zw) * w), int((zy + zh) * h)),
                              (165, 110, 58), 2)
                cv2.putText(frame, lims, (int(zx * w), int(zy * h) - 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (165, 110, 58), 2)
            cv2.putText(frame, f"hand raises: {len(engine.events)}", (10, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (60, 60, 60), 2)
        elif isinstance(engine, Mode2Engine):
            total = sum(engine.raises_by_minute.values())
            cv2.putText(frame, f"class hand raises: {total}", (10, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (60, 60, 60), 2)

    # -- preview ----------------------------------------------------------

    def mjpeg(self):
        boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
        while not self._stop_flag:
            jpg = self._latest_jpeg
            if jpg is not None:
                yield boundary + jpg + b"\r\n"
            time.sleep(0.08)
