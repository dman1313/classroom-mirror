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


# BGR colors (OpenCV order). Green = movement, per teacher request.
_GREEN = (0, 200, 0)
_MUTED = (90, 90, 90)


def draw_overlay_boxes(frame_bgr, boxes, *, show_numbers: bool = True):
    """Draw movement overlays on ``frame_bgr`` in place and return it.

    ``boxes`` is an iterable of dicts with a normalized ``bbox``
    ``(x, y, w, h)`` in [0, 1], a ``moving`` flag, and an anonymous
    ``number``. Moving people get a thick green rectangle (and their number
    when ``show_numbers``); non-moving people get a thin muted rectangle.
    This mutates a caller-owned copy only; frames are never persisted.
    """
    import cv2

    h, w = frame_bgr.shape[:2]
    for box in boxes:
        bx, by, bw, bh = box["bbox"]
        x1 = max(0, min(w - 1, int(round(bx * w))))
        y1 = max(0, min(h - 1, int(round(by * h))))
        x2 = max(0, min(w - 1, int(round((bx + bw) * w))))
        y2 = max(0, min(h - 1, int(round((by + bh) * h))))
        moving = bool(box.get("moving"))
        color = _GREEN if moving else _MUTED
        thickness = 3 if moving else 1
        cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), color, thickness)
        if moving and show_numbers and box.get("number") is not None:
            label = f"#{box['number']}"
            ty = y1 - 8 if y1 - 8 > 8 else y1 + 18
            cv2.putText(
                frame_bgr,
                label,
                (x1, ty),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                _GREEN,
                2,
                cv2.LINE_AA,
            )
    return frame_bgr
