"""Teacher UX: setup clarity, live legend/counts/timer, macOS permission help.

The pages are server-rendered HTML strings, so these assert on the rendered
markup and on the small amount of state plumbing behind the live timer.
"""

from __future__ import annotations


def test_setup_page_offers_quick_test_and_sensitivity_and_permission_help():
    from v2_app import ui

    html = ui.setup_page([{"index": 1, "backend": "AVFOUNDATION"}])
    assert "1-minute quick test" in html
    assert "duration_minutes" in html
    assert "Camera 1 (AVFOUNDATION)" in html
    assert "Sensitivity" in html
    # macOS permission guidance is available on the setup page.
    assert "Privacy &amp; Security" in html
    assert "Terminal" in html


def test_setup_page_handles_no_camera_found():
    from v2_app import ui

    html = ui.setup_page([])
    assert "No camera found" in html
    assert "Plug in the USB camera" in html


def test_live_page_has_green_legend_counts_and_timer_and_reconnect():
    from v2_app import ui

    html = ui.live_page()
    # Legend explicitly explains green = moving.
    assert "Green box = moving right now" in html
    # Prominent counts.
    assert 'id="peopleCount"' in html
    assert 'id="movingCount"' in html
    # Countdown timer for the quick test.
    assert 'id="timer"' in html
    assert "duration_minutes" in html
    # Robust polling: reconnect + lost-connection handling.
    assert "Reconnecting to the camera" in html
    assert "Lost connection to the app" in html
    # Big, obvious stop that leads to the recap.
    assert "Stop &amp; see recap" in html
    # Permission help is embedded for camera failures.
    assert "macOS permission steps" in html


def test_state_endpoint_exposes_duration_and_elapsed(monkeypatch, tmp_path):
    monkeypatch.setenv("CLASSROOM_MIRROR_DATA_DIR", str(tmp_path / "data"))
    import cv2
    import numpy as np
    from fastapi.testclient import TestClient

    from v2_app import capture as capture_mod
    from v2_app.server import create_app

    frame = np.full((48, 64, 3), 120, dtype=np.uint8)

    class _Cap:
        def __init__(self, index):
            self.index = index

        def isOpened(self):
            return True

        def read(self):
            return True, frame.copy()

        def release(self):
            pass

    monkeypatch.setattr(cv2, "VideoCapture", lambda index: _Cap(index))
    monkeypatch.setattr(capture_mod, "detect_faces_bgr", lambda f: [])

    with TestClient(create_app()) as client:
        assert client.post(
            "/api/start",
            json={"camera_index": 0, "sensitivity": "low", "duration_minutes": 1},
        ).status_code == 200
        body = client.get("/api/state").json()
        assert body["duration_minutes"] == 1
        assert "seconds_elapsed" in body
        assert body["seconds_elapsed"] >= 0
        client.post("/api/stop", json={})


def test_start_rejects_negative_duration(monkeypatch, tmp_path):
    monkeypatch.setenv("CLASSROOM_MIRROR_DATA_DIR", str(tmp_path / "data"))
    from fastapi.testclient import TestClient

    from v2_app.server import create_app

    with TestClient(create_app()) as client:
        r = client.post(
            "/api/start",
            json={"camera_index": 0, "sensitivity": "low", "duration_minutes": -3},
        )
        assert r.status_code == 400
