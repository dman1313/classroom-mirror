"""Frame sources for the V2 movement dashboard.

Two interchangeable sources feed the same privacy-safe analytics:

* ``SyntheticSource`` renders abstract moving shapes with NumPy. It needs no
  hardware, so the whole product can be demonstrated and tested on a headless
  machine (the adult-only alpha) without ever pointing a camera at anyone.
* ``OpenCVCameraSource`` opens exactly one explicitly selected USB camera and
  reads frames into memory. OpenCV is imported lazily so the dashboard and its
  tests run without it.

Neither source encodes, saves, or returns pixels to anywhere but the in-memory
analytics. No frame is ever written to disk or turned into an encoded image.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from .camera import validate_camera_index


class FrameSource(Protocol):
    def read(self) -> np.ndarray | None: ...

    def release(self) -> None: ...

    @property
    def label(self) -> str: ...


@dataclass
class _Mover:
    x: float
    y: float
    vx: float
    vy: float
    size: int
    amplitude: float
    span: float = 0.12


class SyntheticSource:
    """Deterministic moving shapes used for the headless adult alpha.

    The scenario intentionally contains a still marker (stays calm), a gentle
    fidget (reaches yellow), and a large mover (reaches red), so the whole
    calm -> yellow -> red pipeline is exercised end to end.
    """

    def __init__(
        self,
        *,
        width: int = 480,
        height: int = 360,
        seed: int = 7,
    ) -> None:
        self.width = int(width)
        self.height = int(height)
        self._rng = np.random.default_rng(seed)
        self._step = 0
        # Three scenarios, each moving at a constant speed and bouncing within a
        # small span so the movement is *sustained* (not a sine that stalls at
        # the turns): a near-still marker (stays calm), a steady fidget (reaches
        # yellow), and a large mover (reaches red). ``amplitude`` is the per-
        # frame speed in normalised units; ``vx`` seeds the bounce direction.
        self._movers = [
            _Mover(x=0.18, y=0.5, vx=1.0, vy=0.0, size=44, amplitude=0.0016, span=0.03),
            _Mover(x=0.5, y=0.45, vx=1.0, vy=0.0, size=44, amplitude=0.005, span=0.09),
            _Mover(x=0.82, y=0.52, vx=1.0, vy=0.0, size=50, amplitude=0.024, span=0.12),
        ]
        self._origin_x = [m.x for m in self._movers]
        # A fixed high-contrast texture per mover so that, like a real person,
        # the whole patch changes when it moves (not just its outline). This
        # yields one solid, trackable motion blob per mover.
        self._textures = [
            self._rng.integers(60, 240, size=(m.size, m.size), dtype=np.uint8)
            for m in self._movers
        ]

    @property
    def label(self) -> str:
        return "synthetic demo (no camera)"

    def read(self) -> np.ndarray:
        self._step += 1
        frame = np.full((self.height, self.width, 3), 24, dtype=np.uint8)
        for index, mover in enumerate(self._movers):
            mover.x += mover.vx * mover.amplitude
            origin = self._origin_x[index]
            if mover.x > origin + mover.span:
                mover.x = origin + mover.span
                mover.vx = -1.0
            elif mover.x < origin - mover.span:
                mover.x = origin - mover.span
                mover.vx = 1.0
            cx = min(0.92, max(0.08, mover.x))
            cy = min(0.9, max(0.1, mover.y))
            self._paint(frame, cx, cy, self._textures[index])
        return frame

    def _paint(self, frame: np.ndarray, cx: float, cy: float, texture: np.ndarray) -> None:
        size = texture.shape[0]
        px = int(cx * (self.width - 1))
        py = int(cy * (self.height - 1))
        half = size // 2
        x0, x1 = max(0, px - half), min(self.width, px + half)
        y0, y1 = max(0, py - half), min(self.height, py + half)
        tx0, ty0 = x0 - (px - half), y0 - (py - half)
        patch = texture[ty0:ty0 + (y1 - y0), tx0:tx0 + (x1 - x0)]
        frame[y0:y1, x0:x1, :] = patch[:, :, None]

    def release(self) -> None:  # noqa: D401 - nothing to free
        return None


class OpenCVCameraSource:
    """Read frames from one explicitly selected USB camera (lazy OpenCV)."""

    def __init__(self, camera_index: int) -> None:
        self.camera_index = validate_camera_index(camera_index)
        import cv2  # noqa: PLC0415 - lazy so headless installs stay import-clean

        self._cv2 = cv2
        self._capture = cv2.VideoCapture(self.camera_index)
        if not self._capture.isOpened():
            self._capture.release()
            from .camera import CameraUnavailable

            raise CameraUnavailable(
                f"Camera {self.camera_index} could not be opened. Check that it is "
                "plugged in, not busy in another app, and allowed in the operating "
                "system's camera privacy settings."
            )

    @property
    def label(self) -> str:
        try:
            backend = self._capture.getBackendName() or "UNKNOWN"
        except Exception:
            backend = "UNKNOWN"
        return f"camera index {self.camera_index} ({backend})"

    def read(self) -> np.ndarray | None:
        ok, frame = self._capture.read()
        if not ok or frame is None or getattr(frame, "size", 0) == 0:
            return None
        return frame

    def release(self) -> None:
        try:
            self._capture.release()
        except Exception:
            pass


def build_source(kind: str, *, camera_index: int | None = None) -> FrameSource:
    """Factory: 'synthetic' for the headless alpha, 'camera' for real hardware."""
    normalized = (kind or "").strip().lower()
    if normalized == "synthetic":
        return SyntheticSource()
    if normalized == "camera":
        if camera_index is None:
            raise ValueError("camera source requires an explicit --camera-index")
        return OpenCVCameraSource(camera_index)
    raise ValueError("source must be 'synthetic' or 'camera'")
