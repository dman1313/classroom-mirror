"""Behavioural coverage for the usable teacher dashboard; made-up data only."""

import math
import time
import socket

from fastapi.testclient import TestClient
import numpy as np
import pytest

from app.heuristics import Person
from v2_app.engine import Engine, PROFILES
from v2_app.demo import demo_people
from v2_app.server import create_app
from v2_app.session import Session
from v2_app.store import Store
from v2_app.__main__ import network_guard

HEADERS = {"X-Classroom-Mirror": "1"}
CONFIG = {
    "source": "demo",
    "sensitivity": "high",
    "duration_minutes": 1,
    "camera_index": 0,
}


def person(x=0.2, up=False):
    return Person(
        {
            "nose": (x + 0.05, 0.2, 1),
            "left_eye": (x + 0.04, 0.2, 1),
            "right_eye": (x + 0.06, 0.2, 1),
            "left_wrist": (x, 0.1 if up else 0.4, 1),
        },
        (x, 0.15, 0.1, 0.5),
    )


def until(predicate, timeout=3):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Expected state did not arrive within the timeout")


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1", headers=HEADERS) as c:
        yield c


def test_practice_reaches_yellow_then_red_and_clears():
    engine = Engine("high")
    history = []
    for i in range(450):
        engine.update(i / 10, demo_people(i / 10))
        history.append([t.band for t in engine.visible])
    assert any("yellow" in bands for bands in history)
    first_yellow = next(i for i, bands in enumerate(history) if "yellow" in bands)
    first_red = next(i for i, bands in enumerate(history) if "red" in bands)
    assert first_red > first_yellow
    assert all(t.band == "calm" for t in engine.visible)
    assert engine.recap()["raises"] > 0


def test_high_only_changes_timing_and_short_motion_never_alerts():
    assert PROFILES["high"].threshold == PROFILES["low"].threshold
    e = Engine("high")
    for i in range(20):
        e.update(i / 10, demo_people(i / 10))
    assert e.yellow_events == e.red_events == 0


def test_occlusion_keeps_position_but_expired_tracks_do_not_reidentify():
    e = Engine()
    e.update(0, [person()])
    first = e.visible[0].number
    e.update(0.2, [])
    e.update(0.5, [person(0.21)])
    assert e.visible[0].number == first
    e.update(3, [person(0.21)])
    assert e.visible[0].number != first
    assert Engine().next_id == 1


def test_one_to_one_matching_and_no_duplicate_number_in_frame():
    e = Engine()
    e.update(0, [person(0.2), person(0.4)])
    e.update(0.1, [person(0.29), person(0.30)])
    assert len({t.number for t in e.visible}) == 2


def test_three_held_raises_count_once_each_and_survive_exit_in_recap():
    e = Engine()
    for i in range(100):
        t = i / 10
        up = 1 <= t < 2 or 4 <= t < 5 or 7 <= t < 8
        e.update(t, [person(up=up)])
    e.update(12, [])
    assert e.recap()["raises"] == 3
    assert e.snapshot()["people"] == 0


def test_non_monotonic_timestamps_rejected():
    e = Engine()
    e.update(1, [])
    for t in (1, 0, math.nan, math.inf):
        with pytest.raises(ValueError):
            e.update(t, [])


def test_start_stop_saves_aggregate_recap_and_history_survives_restart(
    client, tmp_path
):
    assert client.post("/api/start", json=CONFIG).status_code == 200
    until(lambda: client.get("/api/state").json().get("frames", 0) > 1)
    assert client.get("/api/state").json()["people"] == 6
    result = client.post("/api/stop").json()
    assert result["status"] == "finished"
    recap = client.get("/api/recaps").json()["recaps"][0]
    assert recap["source"] == "demo" and recap["peak_people"] == 6
    assert (
        not {"tracks", "bbox", "keypoints", "number", "names", "embeddings"}
        & recap.keys()
    )
    db = Store(tmp_path)
    assert db.list()[0]["id"] == recap["id"]
    db.close()
    assert {p.suffix for p in tmp_path.iterdir()} <= {".sqlite3"}


def test_invalid_configuration_and_adult_gate_prevent_capture(client):
    assert (
        client.post("/api/start", json={**CONFIG, "source": "camera"}).status_code
        == 400
    )
    for patch in (
        {"source": "remote"},
        {"camera_index": True},
        {"camera_index": -1},
        {"camera_index": 10},
        {"duration_minutes": 0},
        {"sensitivity": "medium"},
        {"name": "not permitted"},
    ):
        assert client.post("/api/start", json={**CONFIG, **patch}).status_code == 422
    assert client.get("/api/state").json()["status"] == "idle"


def test_duplicate_start_does_not_replace_session(client):
    client.post("/api/start", json=CONFIG)
    assert (
        client.post("/api/start", json={**CONFIG, "sensitivity": "low"}).status_code
        == 409
    )
    assert client.get("/api/state").json()["sensitivity"] == "high"


def test_hide_blocks_frames_counters_and_history(client):
    client.post("/api/start", json=CONFIG)
    until(lambda: client.get("/api/state").json().get("people") == 6)
    client.app.state.session.jpeg = b"fake private pixels"
    assert client.post("/api/hide", json={"hidden": True}).status_code == 200
    assert client.get("/api/state").json() == {"status": "running", "hidden": True}
    assert client.get("/api/preview.jpg").status_code == 204
    assert client.get("/api/recaps").status_code == 423
    client.post("/api/hide", json={"hidden": False})
    assert client.get("/api/state").json()["people"] == 6


def test_stop_is_idempotent_and_does_not_create_duplicate_recaps(client):
    client.post("/api/start", json=CONFIG)
    until(lambda: client.get("/api/state").json().get("frames", 0) > 1)
    client.post("/api/stop")
    client.post("/api/stop")
    assert len(client.get("/api/recaps").json()["recaps"]) == 1


def test_server_timer_ends_session_without_browser_action(client):
    client.post("/api/start", json=CONFIG)
    until(lambda: client.get("/api/state").json().get("frames", 0) > 0)
    client.app.state.session.duration = 0.2
    until(lambda: client.app.state.session.status == "finished")
    assert client.get("/api/recaps").json()["recaps"][0]["end_reason"] == "timer"


def test_disconnected_browser_releases_session(client):
    client.post("/api/start", json=CONFIG)
    until(lambda: client.get("/api/state").json().get("frames", 0) > 0)
    client.app.state.session.heartbeat = time.monotonic() - 31
    until(lambda: client.app.state.session.status == "finished")
    assert (
        client.get("/api/recaps").json()["recaps"][0]["end_reason"]
        == "dashboard_closed"
    )


def test_delete_one_all_and_expiry_remove_saved_records(client):
    store = client.app.state.store
    one = store.save({"source": "demo"})
    two = store.save({"source": "demo"})
    client.delete(f"/api/recaps/{one}")
    assert [r["id"] for r in store.list()] == [two]
    with store.lock:
        store.db.execute("UPDATE recaps SET created=?", (time.time() - 31 * 86400,))
        store.db.commit()
    assert store.list() == []
    store.save({"source": "demo"})
    client.delete("/api/recaps")
    assert store.list() == []


def test_web_origin_and_host_checks_prevent_cross_site_camera_control(client):
    for headers in (
        {"Origin": "https://unrelated.example"},
        {"Host": "evil.example"},
        {"Sec-Fetch-Site": "cross-site"},
        {"X-Classroom-Mirror": ""},
    ):
        assert (
            client.post("/api/start", json=CONFIG, headers=headers).status_code == 403
        )
    r = client.get("/")
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-frame-options"] == "DENY"
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert client.get("/api/state").json()["status"] == "idle"


def test_camera_failure_releases_device_and_does_not_fake_success(tmp_path):
    class BrokenCamera:
        released = False

        def isOpened(self):
            return True

        def read(self):
            return False, None

        def release(self):
            self.released = True

    camera = BrokenCamera()
    store = Store(tmp_path)
    session = Session(
        store, capture_factory=lambda index: camera, vision_factory=lambda: object()
    )
    session.start({**CONFIG, "source": "camera"})
    until(lambda: session.status == "error")
    assert camera.released
    assert "stopped sending" in session.error
    assert store.list() == []
    session.shutdown()
    store.close()


def test_fake_camera_frames_are_only_encoded_in_memory_and_released(
    tmp_path, monkeypatch
):
    import cv2

    def forbidden(*args, **kwargs):
        raise AssertionError("Media writes must never happen")

    monkeypatch.setattr(cv2, "imwrite", forbidden)
    monkeypatch.setattr(cv2, "VideoWriter", forbidden)

    class Camera:
        released = False

        def isOpened(self):
            return True

        def read(self):
            return True, np.zeros((32, 64, 3), dtype=np.uint8)

        def release(self):
            self.released = True

    class Vision:
        def detect(self, frame):
            return [person()]

    camera = Camera()
    store = Store(tmp_path)
    session = Session(
        store, capture_factory=lambda index: camera, vision_factory=Vision
    )
    session.start({**CONFIG, "source": "camera"})
    until(lambda: session.preview() is not None)
    assert session.preview().startswith(b"\xff\xd8")
    session.hide(True)
    assert session.preview() is None
    session.stop()
    assert camera.released and session.jpeg is None
    assert {p.suffix for p in tmp_path.iterdir()} <= {".sqlite3"}
    store.close()


def test_runtime_audit_guard_rejects_outbound_network_before_connection():
    with socket.socket() as sock:
        for event in ("socket.connect", "socket.bind"):
            with pytest.raises(PermissionError):
                network_guard(event, (sock, ("8.8.8.8", 443)))
            network_guard(event, (sock, ("127.0.0.1", 8470)))
    with pytest.raises(PermissionError):
        network_guard("socket.getaddrinfo", ("example.com", 443, 0, 0, 0))
