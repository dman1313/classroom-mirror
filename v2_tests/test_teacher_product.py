"""V2 teacher-product acceptance: YOLO identity, alerts, recap, privacy."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.heuristics import Person
from v2_app.alerts import BAND_NONE, BAND_RED, BAND_YELLOW, AlertState, update_alert
from v2_app.engine import LIVE_OCCLUDE_SECONDS, Detection, SessionEngine
from v2_app.identity import MATCH_FLOOR, IdentityBook, cosine, vector_from_gray
from v2_app.sensitivity import get_profile
from v2_app.store import FORBIDDEN_COLUMNS, Store
from v2_app.vision import PoseVision, head_box


ROOT = Path(__file__).resolve().parents[1]


def _person(bbox, kps=None) -> Person:
    return Person(kps=kps or {}, bbox=bbox)


def _vector(seed: int, noise: float = 0.0) -> list[float]:
    rng = np.random.default_rng(seed)
    gray = rng.normal(128, 40, size=(64, 64)).astype(np.float32)
    if noise:
        gray = gray + rng.normal(0, noise, size=gray.shape).astype(np.float32)
    return vector_from_gray(gray)


class FakePoseDetector:
    def __init__(self, persons_by_call=None):
        self.persons_by_call = list(persons_by_call or [])
        self.calls = 0

    def detect(self, frame_bgr):
        self.calls += 1
        if self.persons_by_call:
            return self.persons_by_call.pop(0)
        return []


def test_vision_uses_yolo_pose_not_haar():
    source = (ROOT / "v2_app" / "vision.py").read_text(encoding="utf-8")
    assert "PoseDetector" in source
    assert "yolo" in source.lower() or "PoseDetector" in source
    assert "haarcascade" not in source.lower()
    capture = (ROOT / "v2_app" / "capture.py").read_text(encoding="utf-8")
    assert "PoseVision" in capture
    assert "detect_faces_bgr" not in capture


def test_head_crop_comes_from_pose_keypoints_in_ram():
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    frame[40:90, 70:120] = (30, 80, 200)
    person = _person(
        (0.2, 0.1, 0.5, 0.8),
        {
            "nose": (0.48, 0.32, 0.9),
            "left_eye": (0.44, 0.28, 0.9),
            "right_eye": (0.52, 0.28, 0.9),
        },
    )
    box = head_box(person, 200, 200)
    assert box is not None
    assert box.w >= 48 and box.h >= 48
    vision = PoseVision(detector=FakePoseDetector([[person]]))
    detections = vision.detections_from_frame(frame)
    assert len(detections) == 1
    assert detections[0].person is person
    assert len(detections[0].vector) == 32 * 32


def test_sticky_id_survives_occlusion_and_later_session(tmp_path, monkeypatch):
    monkeypatch.setenv("CLASSROOM_MIRROR_DATA_DIR", str(tmp_path / "data"))
    store = Store()
    engine = SessionEngine(store.book, "low")
    first = _vector(1)
    engine.ingest(0.0, [Detection(bbox=(0.1, 0.1, 0.2, 0.4), vector=first)])
    number = next(iter(engine.students))
    engine.ingest(1.0, [])
    assert number in engine.students
    similar = _vector(1, noise=2.0)
    engine.ingest(3.0, [Detection(bbox=(0.12, 0.11, 0.2, 0.4), vector=similar)])
    assert list(engine.students) == [number]
    store.persist_book()
    store.close()

    later = Store()
    engine2 = SessionEngine(later.book, "low")
    stored = next(iter(later.book.identities.values())).vector
    engine2.ingest(10.0, [Detection(bbox=(0.1, 0.1, 0.2, 0.4), vector=stored)])
    assert list(engine2.students) == [number]


def test_match_floor_rejects_a_different_person():
    book = IdentityBook()
    book.match_or_create(_vector(7), 0.0)
    other = _vector(99)
    number, score = book.match_or_create(other, 1.0)
    assert number == 2
    assert score == 1.0
    assert cosine(_vector(7), other) < MATCH_FLOOR


def test_templates_expire_and_delete():
    book = IdentityBook()
    n, _ = book.match_or_create(_vector(3), 0.0)
    book.expire(now=40 * 24 * 3600)
    assert n not in book.identities
    a, _ = book.match_or_create(_vector(4), 0.0)
    b, _ = book.match_or_create(_vector(5), 1.0)
    assert book.delete_one(a)
    assert a not in book.identities
    assert b in book.identities
    assert book.delete_all() == 1
    assert book.identities == {}


def test_yellow_precedes_red_and_brief_motion_clears():
    profile = get_profile("low")
    state = AlertState()
    t = 0.0
    while t < profile.yellow_hold - 0.5:
        update_alert(state, t, profile.speed_threshold + 0.01, profile)
        t += 0.5
    assert state.band == BAND_NONE
    update_alert(state, t + profile.yellow_hold, profile.speed_threshold + 0.01, profile)
    assert state.band == BAND_YELLOW
    update_alert(
        state,
        t + profile.yellow_hold + profile.red_hold,
        profile.speed_threshold + 0.01,
        profile,
    )
    assert state.band == BAND_RED

    brief = AlertState()
    update_alert(brief, 0.0, profile.speed_threshold + 0.2, profile)
    update_alert(brief, 0.4, None, profile)
    update_alert(brief, 0.4 + profile.recover_hold, None, profile)
    assert brief.band == BAND_NONE


def test_high_sensitivity_is_timing_only():
    low = get_profile("low")
    high = get_profile("high")
    assert low.version == high.version
    assert high.speed_threshold == low.speed_threshold
    assert high.yellow_hold < low.yellow_hold
    assert high.red_hold < low.red_hold
    assert high.recover_hold < low.recover_hold


def test_profile_locks_after_start():
    engine = SessionEngine(IdentityBook(), "high")
    assert engine.locked_profile_key == "high"
    assert engine.profile.key == "high"
    engine.ingest(0.0, [Detection(bbox=(0.1, 0.1, 0.2, 0.5), vector=_vector(8))])
    assert engine.snapshot()["sensitivity"] == "high"


def test_hand_raise_counts_on_synthetic_keypoints():
    kps = {
        "left_eye": (0.4, 0.4, 0.9),
        "right_eye": (0.5, 0.4, 0.9),
        "nose": (0.45, 0.42, 0.9),
        "left_wrist": (0.4, 0.10, 0.9),
        "right_wrist": (0.5, 0.55, 0.4),
    }
    person = _person((0.3, 0.2, 0.3, 0.6), kps)
    engine = SessionEngine(IdentityBook(), "low")
    vec = _vector(11)
    engine.ingest(0.0, [Detection(bbox=person.bbox, vector=vec, person=person)])
    engine.ingest(0.6, [Detection(bbox=person.bbox, vector=vec, person=person)])
    assert engine.room_raises == 1
    st = next(iter(engine.students.values()))
    assert st.raises == 1


def test_live_hide_and_recap_wording():
    engine = SessionEngine(IdentityBook(), "low")
    engine.ingest(0.0, [Detection(bbox=(0.1, 0.1, 0.2, 0.4), vector=_vector(12))])
    engine.hidden = True
    snap = engine.snapshot()
    assert snap["hidden"] is True
    assert snap["students"] == []
    recap = engine.recap()
    assert "uncertain" in recap["support_copy"]
    assert "grading" in recap["support_copy"]
    assert "ranking" not in recap["support_copy"].lower()
    for row in recap["students"]:
        assert "name" not in row
        assert "lims" not in row


def test_occluded_number_stays_assigned_after_gap():
    engine = SessionEngine(IdentityBook(), "low")
    vec = _vector(13)
    engine.ingest(0.0, [Detection(bbox=(0.2, 0.2, 0.2, 0.4), vector=vec)])
    number = next(iter(engine.students))
    engine.ingest(LIVE_OCCLUDE_SECONDS + 1.0, [])
    live = engine.snapshot()
    assert live["students"] == []
    engine.ingest(LIVE_OCCLUDE_SECONDS + 2.0, [Detection(bbox=(0.21, 0.2, 0.2, 0.4), vector=vec)])
    assert next(iter(engine.students)) == number
    assert engine.snapshot()["students"][0]["number"] == number


def test_store_schema_has_no_names_and_writes_no_media(tmp_path, monkeypatch):
    monkeypatch.setenv("CLASSROOM_MIRROR_DATA_DIR", str(tmp_path / "data"))
    store = Store()
    store.book.match_or_create(_vector(20), 0.0)
    sid = store.record_session("2026-09-06T00:00:00Z", "low")
    store.finish_session(sid, "2026-09-06T00:10:00Z", '{"students":[]}')
    store.persist_book()
    cols = []
    for (table,) in store._conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        if str(table).startswith("sqlite_"):
            continue
        cols.extend(
            r[1].lower()
            for r in store._conn.execute(f"PRAGMA table_info({table})").fetchall()
        )
    for forbidden in FORBIDDEN_COLUMNS:
        assert forbidden not in cols
    store.close()
    written = {path.suffix.lower() for path in (tmp_path / "data").rglob("*") if path.is_file()}
    assert ".jpg" not in written
    assert ".png" not in written
    assert ".mp4" not in written
    assert (tmp_path / "data" / "state" / "identities.bin").is_file()


def test_teacher_http_surface_is_loopback_only_and_has_no_name_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("CLASSROOM_MIRROR_DATA_DIR", str(tmp_path / "data"))
    from v2_app.capture import CaptureLoop
    from v2_app.server import create_app, HOST
    from v2_runtime.policy import validate_bind_host

    assert validate_bind_host(HOST) == "127.0.0.1"
    with patch("v2_app.server.inventory_cameras", return_value=[]), patch.object(
        CaptureLoop, "start", lambda self: None
    ), patch.object(CaptureLoop, "stop", lambda self: None):
        app = create_app()
        client = TestClient(app)
        home = client.get("/").text.lower()
        assert "teacher-only" in home
        assert "lims" not in home
        health = client.get("/health").json()
        assert health["ok"] is True
        assert health["host"] == "127.0.0.1"

        start = client.post(
            "/api/start",
            json={"camera_index": 0, "sensitivity": "low"},
        )
        assert start.status_code == 200
        hide = client.post("/api/hide")
        assert hide.status_code == 200
        stop = client.post("/api/stop")
        assert stop.status_code == 200
        recap = client.get("/api/recap")
        assert recap.status_code == 200
        body = recap.json()
        assert "uncertain" in body["support_copy"]
        wipe = client.post("/api/delete-all")
        assert wipe.status_code == 200
        recap_after = client.get("/api/recap").json()
        assert recap_after["students"] == []

        bad = client.post("/api/start", json={"camera_index": "desk", "sensitivity": "low"})
        assert bad.status_code == 400


def test_recap_delete_one_drops_that_number(tmp_path, monkeypatch):
    monkeypatch.setenv("CLASSROOM_MIRROR_DATA_DIR", str(tmp_path / "data"))
    from v2_app.capture import CaptureLoop
    from v2_app.server import create_app

    with patch("v2_app.server.inventory_cameras", return_value=[]), patch.object(
        CaptureLoop, "start", lambda self: None
    ), patch.object(CaptureLoop, "stop", lambda self: None):
        app = create_app()
        client = TestClient(app)
        assert client.post("/api/start", json={"camera_index": 0, "sensitivity": "low"}).status_code == 200
        engine = app.state.classroom.engine
        assert engine is not None
        engine.ingest(0.0, [Detection(bbox=(0.1, 0.1, 0.2, 0.4), vector=_vector(31))])
        number = next(iter(engine.students))
        assert client.post("/api/stop").status_code == 200
        recap = client.get("/api/recap").json()
        assert recap["students"][0]["number"] == number
        assert client.post(f"/api/delete/{number}").json()["ok"] is True
        assert client.get("/api/recap").json()["students"] == []


def test_occlusion_gap_does_not_count_as_fidget():
    engine = SessionEngine(IdentityBook(), "high")
    vec = _vector(21)
    first = _person((0.10, 0.10, 0.20, 0.50))
    engine.ingest(0.0, [Detection(bbox=first.bbox, vector=vec, person=first)])
    moved = _person((0.70, 0.10, 0.20, 0.50))
    engine.ingest(10.0, [Detection(bbox=moved.bbox, vector=vec, person=moved)])
    student = next(iter(engine.students.values()))
    assert student.speed is None
    assert student.alert.band == BAND_NONE


def test_hmac_template_wrap_roundtrip_and_tamper():
    from v2_app import crypto

    key = b"k" * 32
    blob = crypto.wrap(b'{"next":1}', key)
    assert blob.startswith(b"CM2T")
    assert crypto.unwrap(blob, key) == b'{"next":1}'
    tampered = blob[:-1] + bytes([blob[-1] ^ 1])
    with pytest.raises(ValueError):
        crypto.unwrap(tampered, key)


def test_pose_stack_is_local_yolo_weights():
    from v2_app.vision import pose_stack_error, pose_weights_path

    assert pose_weights_path().name == "yolo11n-pose.pt"
    err = pose_stack_error()
    assert err is None or "install.sh" in err


def test_live_and_setup_pages_stay_teacher_only():
    from v2_app import ui

    setup = ui.setup_page([], None).lower()
    assert "teacher-only" in setup
    assert "disabled" in setup
    assert "no names" in setup
    assert "lims" not in setup
    live = ui.live_page().lower()
    assert "room hand-raises" in live
    assert "show numbers" in live
    assert 'id="error"' in live
    recap = ui.recap_page().lower()
    assert "delete all anonymous numbers" in recap
    assert "lims" not in recap


def test_mac_product_launcher_uses_full_venv_not_haar():
    command = (ROOT / "run-v2.command").read_text(encoding="utf-8")
    assert "v2_runtime.mac_launcher" in command
    assert ".venv/bin/python" in command
    assert "--smoke-test" in command
    assert "app.main" not in command
    launcher = (ROOT / "v2_runtime" / "mac_launcher.py").read_text(encoding="utf-8")
    assert "pose_stack_error" in launcher
    assert "serve_product" in launcher

