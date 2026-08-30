"""Shared V2 camera inventory and bounded in-memory smoke operations.

OpenCV documents explicit device indexes, open checks, frame reads, backend
names, and release here:
https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Callable, Iterable, Protocol


MAX_CAMERA_INDEX = 9


class Capture(Protocol):
    def isOpened(self) -> bool: ...

    def read(self): ...

    def getBackendName(self) -> str: ...

    def release(self) -> None: ...


CaptureFactory = Callable[[int], Capture]


class CameraUnavailable(RuntimeError):
    """The explicitly selected camera could not provide in-memory frames."""


class CameraAbsent(CameraUnavailable):
    """The selected camera is not connected or no longer available."""


class CameraBusy(CameraUnavailable):
    """The selected camera is already held by another application."""


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
        backend = capture.getBackendName() or "UNKNOWN"
    except Exception:
        return "UNKNOWN"
    if not isinstance(backend, str) or not re.fullmatch(r"[A-Za-z0-9 _-]{1,32}", backend):
        return "UNKNOWN"
    return backend


def inventory_display_rows(cameras: Iterable[CameraInfo]) -> tuple[str, ...]:
    """Return stable picker labels containing no driver paths or identifiers."""
    return tuple(
        f"Camera {position} (index {camera.index})"
        for position, camera in enumerate(cameras, start=1)
    )


def _translated_camera_error(index: int, exc: BaseException) -> CameraUnavailable:
    if isinstance(exc, PermissionError):
        return CameraPermissionDenied(
            f"Camera {index} permission denied. Open Windows Privacy & security > "
            "Camera (ms-settings:privacy-webcam), allow desktop apps, and try again. "
            "No fallback camera was attempted."
        )
    if isinstance(exc, BlockingIOError):
        return CameraBusy(
            f"Camera {index} is busy in another app. Close the other app and try "
            "again. No fallback camera was attempted."
        )
    return CameraAbsent(
        f"Camera {index} is not available. Check that it is plugged in and still "
        "selected. No fallback camera was attempted."
    )


def open_camera(
    camera_index: int,
    *,
    capture_factory: CaptureFactory | None = None,
) -> Capture:
    """Open exactly the selected index or raise one plain-language failure."""
    index = validate_camera_index(camera_index)
    factory = capture_factory or _opencv_capture
    try:
        capture = factory(index)
    except (PermissionError, BlockingIOError, OSError) as exc:
        raise _translated_camera_error(index, exc) from exc
    try:
        if not capture.isOpened():
            raise CameraAbsent(
                f"Camera {index} is not available. Check that it is plugged in and "
                "still selected. No fallback camera was attempted."
            )
    except Exception:
        capture.release()
        raise
    return capture


def read_memory_frame(capture: Capture, camera_index: int):
    """Read one non-empty frame without encoding, logging, or persisting it."""
    try:
        ok, frame = capture.read()
    except (PermissionError, BlockingIOError, OSError) as exc:
        raise _translated_camera_error(camera_index, exc) from exc
    if not ok or frame is None or getattr(frame, "size", 1) == 0:
        raise CameraUnavailable(
            f"Camera {camera_index} stopped sending frames. It was released; no "
            "fallback camera was attempted."
        )
    return frame


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
        capture = None
        try:
            capture = factory(index)
            if capture.isOpened():
                cameras.append(CameraInfo(index, _backend_name(capture)))
        except (PermissionError, BlockingIOError, OSError):
            continue
        finally:
            if capture is not None:
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

    capture = open_camera(index, capture_factory=capture_factory)
    started = clock()
    frame_count = 0
    backend = "UNKNOWN"
    elapsed = 0.0
    try:
        backend = _backend_name(capture)
        while True:
            elapsed = clock() - started
            if elapsed >= seconds:
                break
            frame = read_memory_frame(capture, index)
            frame_count += 1
            sleeper(0.01)
    finally:
        capture.release()

    if frame_count == 0:
        raise CameraUnavailable(f"Camera {index} returned no frames during the smoke.")
    return CameraSmokeResult(index, backend, frame_count, elapsed)
