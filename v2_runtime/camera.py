"""Shared V2 camera inventory and bounded in-memory smoke operations.

OpenCV documents explicit device indexes, open checks, frame reads, backend
names, and release here:
https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable, Protocol


MAX_CAMERA_INDEX = 9


class Capture(Protocol):
    def isOpened(self) -> bool: ...

    def read(self): ...

    def getBackendName(self) -> str: ...

    def release(self) -> None: ...


CaptureFactory = Callable[[int], Capture]


class CameraUnavailable(RuntimeError):
    """The explicitly selected camera could not provide in-memory frames."""


class CameraBusy(CameraUnavailable):
    """The selected camera exists but is already held by another process."""


class CameraPermissionDenied(CameraUnavailable):
    """The operating system denied access to the selected camera."""


@dataclass(frozen=True)
class CameraInfo:
    index: int
    backend: str


@dataclass(frozen=True)
class CameraSmokeResult:
    camera_index: int
    backend: str
    frame_count: int
    elapsed_seconds: float


def validate_camera_index(index: object) -> int:
    """Accept only a bounded explicit device index; never guess or fall back."""
    if isinstance(index, bool) or not isinstance(index, int):
        raise ValueError("camera index must be an integer from 0 through 9")
    if not 0 <= index <= MAX_CAMERA_INDEX:
        raise ValueError("camera index must be an integer from 0 through 9")
    return index


def _opencv_capture(index: int) -> Capture:
    import cv2

    return cv2.VideoCapture(index)


def _backend_name(capture: Capture) -> str:
    try:
        return capture.getBackendName() or "UNKNOWN"
    except Exception:
        return "UNKNOWN"


def inventory_cameras(
    *,
    max_index: int = 5,
    capture_factory: CaptureFactory | None = None,
) -> list[CameraInfo]:
    """Probe bounded local indexes and return text-only picker rows."""
    validate_camera_index(max_index)
    factory = capture_factory or _opencv_capture
    cameras: list[CameraInfo] = []
    for index in range(max_index + 1):
        capture = factory(index)
        try:
            if capture.isOpened():
                cameras.append(CameraInfo(index, _backend_name(capture)))
        finally:
            capture.release()
    return cameras


def smoke_camera(
    camera_index: int,
    *,
    seconds: float = 3.0,
    capture_factory: CaptureFactory | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> CameraSmokeResult:
    """Read bounded frames from exactly one camera and always release it."""
    index = validate_camera_index(camera_index)
    if not 0 < seconds <= 30:
        raise ValueError("smoke duration must be greater than 0 and at most 30 seconds")

    factory = capture_factory or _opencv_capture
    try:
        capture = factory(index)
    except PermissionError as exc:
        raise CameraPermissionDenied(
            f"Camera {index} access was denied by the operating system. No "
            "fallback camera was attempted."
        ) from exc
    except OSError as exc:
        raise CameraBusy(
            f"Camera {index} is present but could not be claimed; it may be in "
            "use by another application. No fallback camera was attempted."
        ) from exc
    started = clock()
    frame_count = 0
    backend = "UNKNOWN"
    elapsed = 0.0
    try:
        if not capture.isOpened():
            raise CameraUnavailable(
                f"Camera {index} could not be opened. Check that it is plugged in, "
                "not busy in another app, and allowed in the operating system's "
                "camera privacy settings. No fallback camera was attempted."
            )
        backend = _backend_name(capture)
        while True:
            elapsed = clock() - started
            if elapsed >= seconds:
                break
            ok, frame = capture.read()
            if not ok or frame is None or getattr(frame, "size", 1) == 0:
                raise CameraUnavailable(
                    f"Camera {index} stopped sending frames. It was released; no "
                    "fallback camera was attempted."
                )
            frame_count += 1
            sleeper(0.01)
    finally:
        capture.release()

    if frame_count == 0:
        raise CameraUnavailable(f"Camera {index} returned no frames during the smoke.")
    return CameraSmokeResult(index, backend, frame_count, elapsed)
