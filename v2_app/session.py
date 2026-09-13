"""One camera worker and one session. The worker owns release and auto-stop."""

from datetime import datetime, timezone
import threading
import time

from .engine import Engine
from .demo import demo_people
from .vision import PoseVision


class Session:
    def __init__(self, store, *, capture_factory=None, vision_factory=PoseVision):
        self.store = store
        self.capture_factory = capture_factory
        self.vision_factory = vision_factory
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread = None
        self.status = "idle"
        self.hidden = False
        self.error = None
        self.jpeg = None
        self.engine = None
        self.last_recap = None
        self.started = None
        self.heartbeat = time.monotonic()
        self.source = "demo"
        self.scan_lock = threading.Lock()

    def start(self, config):
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ValueError(
                    "A session is already running. Stop it before starting another."
                )
            self.source = config["source"]
            self.camera_index = config["camera_index"]
            self.duration = config["duration_minutes"] * 60
            self.engine = Engine(config["sensitivity"])
            self.status, self.error = "starting", None
            self.hidden, self.jpeg = False, None
            self.started = None
            self.last_recap = None
            self.heartbeat = time.monotonic()
            self.stop_event = threading.Event()
            self.thread = threading.Thread(
                target=self._run, daemon=True, name="classroom-session"
            )
            self.thread.start()

    def stop(self):
        with self.lock:
            if self.thread and self.thread.is_alive():
                self.status = "stopping"
            self.stop_event.set()
            self.jpeg = None
        # Never wait for a worker while holding the worker's lock.
        if self.thread:
            self.thread.join(timeout=2)
        return self.snapshot(touch=False)

    def shutdown(self):
        self.stop()
        if self.thread:
            self.thread.join(timeout=10)

    def hide(self, hidden):
        with self.lock:
            self.hidden = hidden
            if hidden:
                self.jpeg = None

    def snapshot(self, touch=True):
        with self.lock:
            if touch:
                self.heartbeat = time.monotonic()
            result = {
                "status": self.status,
                "hidden": self.hidden,
                "last_recap": self.last_recap,
                "error": self.error,
                "source": self.source,
            }
            if self.hidden:
                return {"status": self.status, "hidden": True}
            elapsed = time.monotonic() - self.started if self.started else 0
            result.update(
                {
                    "elapsed": round(elapsed, 1),
                    "duration": getattr(self, "duration", 0),
                    "sensitivity": self.engine.sensitivity if self.engine else "low",
                }
            )
            if self.engine:
                result.update(self.engine.snapshot())
            return result

    def preview(self):
        with self.lock:
            return None if self.hidden or self.status != "running" else self.jpeg

    def _run(self):
        capture = None
        reason = "stopped"
        try:
            if self.source == "camera":
                detector = self.vision_factory()
                if self.stop_event.is_set():
                    return
                # Camera selection and inventory cannot contend for the device.
                with self.scan_lock:
                    factory = self.capture_factory
                    if factory is None:
                        import cv2

                        factory = cv2.VideoCapture
                    capture = factory(self.camera_index)
                    if not capture.isOpened():
                        raise RuntimeError(
                            f"Camera {self.camera_index} could not open. Close Zoom or FaceTime and check camera permission for Terminal or Codex in System Settings."
                        )
                    if hasattr(capture, "set"):
                        import cv2

                        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
                        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
                        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            with self.lock:
                self.started = time.monotonic()
                self.started_iso = datetime.now(timezone.utc).isoformat()
                self.status = "running"
            while not self.stop_event.is_set():
                now = time.monotonic()
                t = now - self.started
                if self.duration and t >= self.duration:
                    reason = "timer"
                    break
                if now - self.heartbeat > 30:
                    reason = "dashboard_closed"
                    break
                if self.source == "demo":
                    persons, jpeg = demo_people(t), None
                else:
                    ok, frame = capture.read()
                    if not ok or frame is None or frame.size == 0:
                        raise RuntimeError(
                            "The camera stopped sending images. It has been released. Reconnect it, then start a new session."
                        )
                    persons = detector.detect(frame)
                    if self.hidden:
                        jpeg = None
                    else:
                        import cv2

                        ok, encoded = cv2.imencode(
                            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75]
                        )
                        jpeg = encoded.tobytes() if ok else None
                    del frame
                with self.lock:
                    if self.stop_event.is_set():
                        break
                    self.engine.update(t, persons)
                    self.jpeg = None if self.hidden else jpeg
                self.stop_event.wait(0.1 if self.source == "demo" else 0.02)
        except Exception as exc:
            with self.lock:
                self.error = (
                    str(exc) or "The session could not start. Please try again."
                )
            reason = "error"
        finally:
            if capture is not None:
                capture.release()
            with self.lock:
                self.jpeg = None
                if self.engine and self.engine.frames:
                    summary = self.engine.recap()
                    summary.update(
                        {
                            "source": self.source,
                            "started_at": self.started_iso,
                            "duration_seconds": round(
                                time.monotonic() - self.started, 1
                            ),
                            "end_reason": reason,
                            "error": self.error,
                        }
                    )
                    try:
                        self.last_recap = self.store.save(summary)
                    except Exception:
                        self.error = "The session ended, but the recap could not be saved. Check free disk space and folder permissions."
                self.engine = None
                self.status = "error" if self.error else "finished"
                self.started = None
