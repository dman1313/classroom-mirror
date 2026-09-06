"""YOLO11 pose detections. Face/head crops exist only as RAM arrays."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.heuristics import MIN_KP_CONF, Person

from .engine import Detection
from .identity import vector_from_gray

WEIGHTS_NAME = "yolo11n-pose.pt"

FACE_KP_NAMES = ("nose", "left_eye", "right_eye", "left_ear", "right_ear")


def pose_weights_path() -> Path:
    return Path(__file__).resolve().parents[1] / WEIGHTS_NAME


def pose_stack_error() -> str | None:
    """Plain-language reason the teacher dashboard cannot run YOLO11 pose."""
    try:
        import ultralytics  # noqa: F401
    except ImportError:
        return (
            "YOLO11 pose is not installed. Run ./install.sh so the teacher "
            "dashboard can use the local pose weights. The camera-only "
            "installer (./install-v2-mac.sh) is not enough."
        )
    if not pose_weights_path().is_file():
        return (
            "The pose model file yolo11n-pose.pt is missing. Run ./install.sh "
            "(it downloads the model once; the app never fetches it later)."
        )
    return None


@dataclass(frozen=True)
class PixelBox:
    x: int
    y: int
    w: int
    h: int


class PoseVision:
    """Load the local YOLO11 pose weights once and turn frames into detections."""

    def __init__(self, detector=None):
        self._detector = detector

    def _load(self):
        if self._detector is None:
            from app.detector import PoseDetector

            self._detector = PoseDetector()
        return self._detector

    def detections_from_frame(self, frame_bgr) -> list[Detection]:
        persons = self._load().detect(frame_bgr)
        detections: list[Detection] = []
        for person in persons:
            gray = head_crop_gray(frame_bgr, person)
            if gray is None:
                continue
            try:
                vector = vector_from_gray(gray)
            except ValueError:
                continue
            detections.append(
                Detection(
                    bbox=person.bbox,
                    vector=vector,
                    person=person,
                )
            )
        return detections


def head_box(person: Person, frame_width: int, frame_height: int) -> PixelBox | None:
    """Pixel box around the head from pose keypoints, else the upper body box."""
    xs: list[float] = []
    ys: list[float] = []
    for name in FACE_KP_NAMES:
        point = person.kps.get(name)
        if point is None or point[2] < MIN_KP_CONF:
            continue
        xs.append(point[0] * frame_width)
        ys.append(point[1] * frame_height)

    if xs and ys:
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        side = max(person.height * frame_height * 0.42, 48.0)
        return _clamp_box(
            int(cx - side / 2),
            int(cy - side / 2),
            int(side),
            int(side),
            frame_width,
            frame_height,
        )

    x, y, width, height = person.bbox
    if width <= 0 or height <= 0:
        return None
    px = int(x * frame_width)
    py = int(y * frame_height)
    pw = int(width * frame_width)
    ph = int(height * frame_height * 0.45)
    return _clamp_box(px, py, pw, ph, frame_width, frame_height)


def head_crop_gray(frame_bgr, person: Person):
    import cv2

    height, width = frame_bgr.shape[:2]
    box = head_box(person, width, height)
    if box is None or box.w < 8 or box.h < 8:
        return None
    roi = frame_bgr[box.y : box.y + box.h, box.x : box.x + box.w]
    if roi.size == 0:
        return None
    return cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)


def _clamp_box(x: int, y: int, w: int, h: int, frame_width: int, frame_height: int) -> PixelBox | None:
    x2 = min(frame_width, max(0, x) + max(0, w))
    y2 = min(frame_height, max(0, y) + max(0, h))
    x1 = min(max(0, x), frame_width)
    y1 = min(max(0, y), frame_height)
    if x2 <= x1 or y2 <= y1:
        return None
    return PixelBox(x1, y1, x2 - x1, y2 - y1)
