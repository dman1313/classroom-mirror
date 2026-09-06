"""In-RAM motion detection for the teacher-only green movement overlay.

Frame differencing only — no faces, no identity, no model download. This is
the classroom-distance-robust path for "green = currently moving": it flags
regions that changed between two consecutive frames, so a mover far from the
camera (whose face is too small for the Haar cascade) still gets a green box.

All work happens on caller-owned RAM arrays. Nothing here writes a frame,
crop, or encoded image to disk; only the previous grayscale frame is held in
memory so the next tick can be compared against it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MotionBox:
    """A currently-moving region, normalized to the frame in [0, 1]."""

    x: float
    y: float
    w: float
    h: float
    area: float  # normalized area (w * h), used for ranking/merging

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.w, self.h)


class MotionTracker:
    """Bounded frame-difference motion detector.

    ``detect`` returns the largest moving regions on the current frame.
    The first frame (or a resolution change) yields no boxes because there
    is nothing to diff against yet.
    """

    def __init__(
        self,
        *,
        min_area_frac: float = 0.0012,
        threshold: int = 22,
        blur: int = 21,
        dilate_iterations: int = 2,
        max_boxes: int = 12,
    ) -> None:
        self.min_area_frac = min_area_frac
        self.threshold = threshold
        # GaussianBlur needs an odd kernel; force it so callers can pass any int.
        self.blur = blur if blur % 2 == 1 else blur + 1
        self.dilate_iterations = dilate_iterations
        self.max_boxes = max_boxes
        self._prev_gray = None

    def reset(self) -> None:
        """Forget the previous frame (e.g. on stop or camera change)."""
        self._prev_gray = None

    def _prepare(self, frame_bgr):
        import cv2

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        return cv2.GaussianBlur(gray, (self.blur, self.blur), 0)

    def detect(self, frame_bgr) -> list[MotionBox]:
        import cv2

        gray = self._prepare(frame_bgr)
        prev = self._prev_gray
        self._prev_gray = gray
        if prev is None or prev.shape != gray.shape:
            return []

        delta = cv2.absdiff(prev, gray)
        thresh = cv2.threshold(delta, self.threshold, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=self.dilate_iterations)
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        h, w = gray.shape[:2]
        frame_area = float(w * h) or 1.0
        boxes: list[MotionBox] = []
        for contour in contours:
            bx, by, bw, bh = cv2.boundingRect(contour)
            area_frac = (bw * bh) / frame_area
            if area_frac < self.min_area_frac:
                continue
            boxes.append(
                MotionBox(
                    x=bx / w,
                    y=by / h,
                    w=bw / w,
                    h=bh / h,
                    area=area_frac,
                )
            )
        boxes.sort(key=lambda b: b.area, reverse=True)
        return boxes[: self.max_boxes]
