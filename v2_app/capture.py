"""Background camera loop. Frames stay in RAM and are dropped each tick."""

from __future__ import annotations

import threading
import time

from v2_runtime.camera import CameraUnavailable, CaptureFactory, open_camera, read_memory_frame

from .engine import SessionEngine
from .vision import PoseVision, pose_stack_error


class CaptureLoop:
    def __init__(
        self,
        engine: SessionEngine,
        camera_index: int,
        *,
        capture_factory: CaptureFactory | None = None,
        vision: PoseVision | None = None,
    ):
        self.engine = engine
        self.camera_index = camera_index
        self._capture_factory = capture_factory
        self.vision = vision or PoseVision()
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
        capture = None
        try:
            if self.vision._detector is None:
                missing = pose_stack_error()
                if missing:
                    self.error = missing
                    return
            capture = open_camera(
                self.camera_index,
                capture_factory=self._capture_factory,
            )
            while not self._stop.is_set():
                frame = read_memory_frame(capture, self.camera_index)
                detections = self.vision.detections_from_frame(frame)
                self.engine.ingest(time.monotonic(), detections)
                del frame
                time.sleep(0.05)
        except CameraUnavailable as exc:
            self.error = str(exc)
        except Exception as exc:
            self.error = str(exc)
        finally:
            if capture is not None:
                capture.release()
