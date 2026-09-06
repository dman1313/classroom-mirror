"""Frame-difference motion overlay: reliable green boxes without face detection.

These tests prove the classroom-distance movement path: a mover with no
detectable face still produces a green box in the teacher-only preview, motion
stays RAM-only, and the live state reports movement counts.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

JPEG_SOI = b"\xff\xd8"
JPEG_EOI = b"\xff\xd9"


def _wait_for(predicate, timeout=3.0, interval=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    return predicate()


def test_motion_tracker_first_frame_has_no_boxes():
    from v2_app.motion import MotionTracker

    tracker = MotionTracker()
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    assert tracker.detect(frame) == []


def test_motion_tracker_static_scene_reports_no_motion():
    from v2_app.motion import MotionTracker

    tracker = MotionTracker()
    frame = np.full((120, 160, 3), 60, dtype=np.uint8)
    tracker.detect(frame)
    assert tracker.detect(frame.copy()) == []


def test_motion_tracker_flags_moving_region():
    from v2_app.motion import MotionTracker

    tracker = MotionTracker()
    base = np.full((120, 160, 3), 60, dtype=np.uint8)
    tracker.detect(base)

    moved = base.copy()
    # A bright block appears in the lower-right quadrant.
    moved[70:110, 100:150, :] = 220
    boxes = tracker.detect(moved)

    assert boxes, "a clearly moving block should produce at least one motion box"
    top = boxes[0]
    cx = top.x + top.w / 2
    cy = top.y + top.h / 2
    assert cx > 0.5 and cy > 0.5, "motion box should sit in the moved (lower-right) area"
    # Normalized geometry stays within the frame.
    assert 0.0 <= top.x <= 1.0 and 0.0 <= top.y <= 1.0
    assert 0.0 < top.w <= 1.0 and 0.0 < top.h <= 1.0


def test_motion_tracker_reset_clears_previous_frame():
    from v2_app.motion import MotionTracker

    tracker = MotionTracker()
    frame = np.full((120, 160, 3), 60, dtype=np.uint8)
    tracker.detect(frame)
    tracker.reset()
    # After reset there is nothing to diff against, so the next frame is quiet.
    assert tracker.detect(frame.copy()) == []


def test_draw_motion_boxes_paints_green():
    from v2_app.motion import MotionBox
    from v2_app.vision import draw_motion_boxes

    frame = np.full((100, 100, 3), 20, dtype=np.uint8)
    draw_motion_boxes(frame, [MotionBox(0.2, 0.2, 0.4, 0.4, 0.16)])
    green = (frame[:, :, 1] > 120) & (frame[:, :, 0] < 90) & (frame[:, :, 2] < 90)
    assert green.any(), "motion boxes should draw green pixels"


def test_draw_overlay_boxes_draws_trail_for_movers():
    import cv2

    from v2_app.vision import draw_overlay_boxes

    frame = np.full((120, 120, 3), 20, dtype=np.uint8)
    draw_overlay_boxes(
        frame,
        [
            {
                "number": 2,
                "bbox": (0.4, 0.4, 0.2, 0.2),
                "moving": True,
                "trail": [(0.1, 0.5), (0.3, 0.5), (0.5, 0.5)],
            }
        ],
    )
    green = (frame[:, :, 1] > 120) & (frame[:, :, 0] < 90) & (frame[:, :, 2] < 90)
    # The trail crosses the left half where no box is drawn, proving the line rendered.
    assert green[:, :40].any(), "movement trail should draw green pixels left of the box"
    _ = cv2


class _AlternatingCapture:
    """Fake camera that alternates two frames so motion diffing sees movement."""

    def __init__(self, index, frame_a, frame_b):
        self.index = index
        self._frames = (frame_a, frame_b)
        self._i = 0

    def isOpened(self):
        return True

    def read(self):
        frame = self._frames[self._i % 2]
        self._i += 1
        return True, frame.copy()

    def release(self):
        pass


def test_capture_publishes_green_motion_without_any_face(monkeypatch):
    import cv2

    from v2_app import capture as capture_mod
    from v2_app.capture import CaptureLoop

    frame_a = np.full((96, 128, 3), 50, dtype=np.uint8)
    frame_b = frame_a.copy()
    frame_b[20:80, 70:120, :] = 210  # a big moving block, no faces at all

    monkeypatch.setattr(
        cv2, "VideoCapture", lambda index: _AlternatingCapture(index, frame_a, frame_b)
    )
    monkeypatch.setattr(capture_mod, "detect_faces_bgr", lambda frame: [])

    class _StubEngine:
        hidden = False

        def ingest(self, *args, **kwargs):
            pass

    def _green_jpeg():
        jpeg = loop.latest_jpeg()
        if not jpeg:
            return None
        decoded = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if decoded is None:
            return None
        green = (
            (decoded[:, :, 1] > 120)
            & (decoded[:, :, 0] < 90)
            & (decoded[:, :, 2] < 90)
        )
        return jpeg if green.any() else None

    loop = CaptureLoop(_StubEngine(), camera_index=0)
    loop.start()
    try:
        # The first tick has nothing to diff against; a later tick shows motion.
        jpeg = _wait_for(_green_jpeg)
        assert jpeg is not None, "motion-only preview should show green boxes without faces"
        assert jpeg.startswith(JPEG_SOI) and jpeg.endswith(JPEG_EOI)
        assert loop.motion_count > 0
    finally:
        loop.stop()
    assert loop.latest_jpeg() is None
    assert loop.motion_count == 0


def test_snapshot_reports_people_and_movement_counts():
    from app.heuristics import Person
    from v2_app.engine import Detection, SessionEngine
    from v2_app.identity import IdentityBook

    engine = SessionEngine(IdentityBook(), "high")
    vec = [1.0] + [0.0] * 1023
    person = Person(kps={}, bbox=(0.1, 0.1, 0.1, 0.2))
    engine.ingest(0.0, [Detection(bbox=(0.1, 0.1, 0.1, 0.2), vector=vec, person=person)])
    # Move fast enough to clear the high-sensitivity speed threshold.
    person2 = Person(kps={}, bbox=(0.6, 0.6, 0.1, 0.2))
    engine.ingest(
        0.2, [Detection(bbox=(0.6, 0.6, 0.1, 0.2), vector=vec, person=person2)]
    )

    snap = engine.snapshot()
    assert snap["people_count"] == 1
    assert snap["moving_count"] >= 1
    assert "movements" not in snap  # merged in by the server, not the engine


def test_state_endpoint_reports_movements(monkeypatch, tmp_path):
    monkeypatch.setenv("CLASSROOM_MIRROR_DATA_DIR", str(tmp_path / "data"))
    import cv2
    from fastapi.testclient import TestClient

    from v2_app import capture as capture_mod
    from v2_app.server import create_app

    frame_a = np.full((96, 128, 3), 50, dtype=np.uint8)
    frame_b = frame_a.copy()
    frame_b[20:80, 70:120, :] = 210

    monkeypatch.setattr(
        cv2, "VideoCapture", lambda index: _AlternatingCapture(index, frame_a, frame_b)
    )
    monkeypatch.setattr(capture_mod, "detect_faces_bgr", lambda frame: [])

    with TestClient(create_app()) as client:
        assert client.post(
            "/api/start", json={"camera_index": 0, "sensitivity": "low"}
        ).status_code == 200

        def _moving_state():
            body = client.get("/api/state").json()
            return body if body.get("moving_regions", 0) > 0 else None

        state = _wait_for(_moving_state)
        assert state is not None, "state should report moving regions from motion diff"
        assert "people_count" in state
        assert state["movements"] >= state["moving_regions"]
        client.post("/api/stop", json={})
