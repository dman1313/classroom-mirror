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
_GREEN_BRIGHT = (40, 255, 40)
_MUTED = (90, 90, 90)
_LABEL_INK = (0, 0, 0)


def _clamp_box(bbox, w: int, h: int) -> tuple[int, int, int, int]:
    bx, by, bw, bh = bbox
    x1 = max(0, min(w - 1, int(round(bx * w))))
    y1 = max(0, min(h - 1, int(round(by * h))))
    x2 = max(0, min(w - 1, int(round((bx + bw) * w))))
    y2 = max(0, min(h - 1, int(round((by + bh) * h))))
    return x1, y1, x2, y2


def _draw_label(frame_bgr, text: str, x: int, y: int, color) -> None:
    """Draw ``text`` with a filled backing box so numbers stay readable."""
    import cv2

    font = cv2.FONT_HERSHEY_SIMPLEX
    scale, thickness = 0.8, 2
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    ty = y - 10 if y - 10 - th > 0 else y + th + 12
    top = ty - th - baseline
    frame_h, frame_w = frame_bgr.shape[:2]
    x = max(0, min(frame_w - tw - 6, x))
    top = max(0, top)
    cv2.rectangle(
        frame_bgr,
        (x, top),
        (min(frame_w - 1, x + tw + 6), min(frame_h - 1, ty + baseline)),
        color,
        -1,
    )
    cv2.putText(
        frame_bgr, text, (x + 3, ty), font, scale, _LABEL_INK, thickness, cv2.LINE_AA
    )


def draw_motion_boxes(frame_bgr, motion_boxes):
    """Draw raw movement regions as bright green boxes (no numbers).

    ``motion_boxes`` is an iterable of objects/dicts exposing a normalized
    ``bbox`` ``(x, y, w, h)``. These come from frame differencing and are the
    primary "currently moving" signal, reliable even when a face is too far to
    detect. Mutates a caller-owned copy only; frames are never persisted.
    """
    import cv2

    h, w = frame_bgr.shape[:2]
    for box in motion_boxes:
        bbox = box["bbox"] if isinstance(box, dict) else box.bbox
        x1, y1, x2, y2 = _clamp_box(bbox, w, h)
        if x2 <= x1 or y2 <= y1:
            continue
        cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), _GREEN_BRIGHT, 3)
    return frame_bgr


def _draw_trail(frame_bgr, trail, w: int, h: int) -> None:
    import cv2

    points = [
        (max(0, min(w - 1, int(round(px * w)))), max(0, min(h - 1, int(round(py * h)))))
        for px, py in trail
    ]
    for i in range(1, len(points)):
        cv2.line(frame_bgr, points[i - 1], points[i], _GREEN, 2, cv2.LINE_AA)


def draw_overlay_boxes(frame_bgr, boxes, *, show_numbers: bool = True):
    """Draw per-person overlays on ``frame_bgr`` in place and return it.

    ``boxes`` is an iterable of dicts with a normalized ``bbox``
    ``(x, y, w, h)`` in [0, 1], a ``moving`` flag, an anonymous ``number``,
    and an optional ``trail`` (list of normalized centroid points). Moving
    people get a thick green rectangle, a short green motion trail, and their
    number in a readable backing label; non-moving people get a thin muted
    rectangle. This mutates a caller-owned copy only; frames are never
    persisted.
    """
    import cv2

    h, w = frame_bgr.shape[:2]
    for box in boxes:
        x1, y1, x2, y2 = _clamp_box(box["bbox"], w, h)
        moving = bool(box.get("moving"))
        color = _GREEN if moving else _MUTED
        thickness = 3 if moving else 1
        cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), color, thickness)
        if moving:
            trail = box.get("trail") or []
            if len(trail) >= 2:
                _draw_trail(frame_bgr, trail, w, h)
        if show_numbers and box.get("number") is not None:
            _draw_label(
                frame_bgr, f"#{box['number']}", x1, y1, color if moving else _MUTED
            )
    return frame_bgr
