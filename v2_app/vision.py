"""In-memory face boxes. Crops exist only as RAM arrays for templating."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FaceHit:
    x: int
    y: int
    w: int
    h: int


_CASCADE = None


def _cascade():
    global _CASCADE
    if _CASCADE is None:
        import cv2

        loaded = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        _CASCADE = loaded
    return _CASCADE


def detect_faces_bgr(frame_bgr) -> list[FaceHit]:
    import cv2

    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    cascade = _cascade()
    if cascade.empty():
        return []
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(48, 48))
    return [FaceHit(int(x), int(y), int(w), int(h)) for x, y, w, h in faces]


def crop_gray(frame_bgr, hit: FaceHit):
    import cv2

    y2 = hit.y + hit.h
    x2 = hit.x + hit.w
    roi = frame_bgr[hit.y:y2, hit.x:x2]
    if roi.size == 0:
        return None
    return cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
