"""Acceptance tests for the first teacher-visible V2 slice: the movement view.

These prove the movement-foundation product behaviour required by V2-DELTA.md
(sticky anonymous numbers, versioned High/Low sensitivity where yellow always
precedes red and brief movement resolves, and an uncertainty-first recap) while
holding the privacy line: loopback only, no pixels sent to the browser, and no
frame-writing/encoding APIs in the new modules.
"""

from __future__ import annotations

from pathlib import Path
import time

import numpy as np
import pytest

from v2_runtime.dashboard import SessionController, create_app, serve
from v2_runtime.engine import MovementEngine
from v2_runtime.policy import PolicyViolation
from v2_runtime.sensitivity import PROFILES, profile_for
from v2_runtime.sources import SyntheticSource, build_source
from v2_runtime.tracking import Marker, MarkerTracker
from v2_runtime.vision import MotionBlob, MotionDetector


ROOT = Path(__file__).resolve().parents[1]
NEW_MODULES = (
    "vision.py",
    "tracking.py",
    "sensitivity.py",
    "engine.py",
    "sources.py",
    "dashboard.py",
)


def _run_engine(profile_name: str, frames: int = 200):
    source = SyntheticSource()
    engine = MovementEngine(profile_for(profile_name))
    history: dict[int, list[str]] = {}
    clock = 0.0
    for _ in range(frames):
        clock += 0.1
        for view in engine.update(source.read(), now=clock):
            history.setdefault(view.number, []).append(view.level)
    return engine, history


# --- Motion analytics -------------------------------------------------------


def test_detector_reports_movement_only_where_a_shape_moves():
    detector = MotionDetector()
    background = np.full((120, 160, 3), 20, dtype=np.uint8)
    detector.update(background)  # prime the previous frame

    moved = background.copy()
    moved[40:70, 60:100, :] = np.random.default_rng(1).integers(
        80, 240, size=(30, 40, 3), dtype=np.uint8
    )
    blobs = detector.update(moved)

    assert blobs, "a moved textured region must produce a motion blob"
    biggest = blobs[0]
    assert 0.25 < biggest.x < 0.75
    assert 0.15 < biggest.y < 0.85


def test_detector_reports_nothing_for_a_static_scene():
    detector = MotionDetector()
    frame = np.full((90, 120, 3), 30, dtype=np.uint8)
    assert detector.update(frame) == []
    assert detector.update(frame.copy()) == []


# --- Anonymous sticky numbers ----------------------------------------------


def test_numbers_are_sticky_and_survive_a_brief_disappearance():
    tracker = MarkerTracker(max_missed=5)
    near = [MotionBlob(x=0.30, y=0.50, energy=0.5, area=0.05)]

    tracker.update(near)
    tracker.update([MotionBlob(x=0.31, y=0.50, energy=0.5, area=0.05)])
    assert [m.number for m in tracker.markers] == [1]

    tracker.update([])  # brief occlusion / missed frame
    tracker.update([MotionBlob(x=0.32, y=0.50, energy=0.5, area=0.05)])
    assert [m.number for m in tracker.markers] == [1], "same number after a gap"


def test_new_region_gets_a_new_number_and_numbers_are_never_reused():
    tracker = MarkerTracker(max_missed=0)
    tracker.update([MotionBlob(x=0.2, y=0.2, energy=0.4, area=0.05)])
    tracker.update([])  # number 1 retires immediately (max_missed=0)
    tracker.update([MotionBlob(x=0.8, y=0.8, energy=0.4, area=0.05)])

    assert [m.number for m in tracker.markers] == [2]
    assert tracker.total_numbers_assigned == 2


def test_synthetic_session_keeps_numbers_stable():
    engine, history = _run_engine("low")
    assert engine.tracker.total_numbers_assigned <= 4
    assert engine._peak_concurrent == 3


# --- Sensitivity and the yellow-before-red rule -----------------------------


def test_high_and_low_share_thresholds_and_privacy_floor():
    high = profile_for("High")
    low = profile_for("Low")
    assert (high.calm_energy, high.yellow_energy, high.red_energy) == (
        low.calm_energy,
        low.yellow_energy,
        low.red_energy,
    )
    assert high.version == low.version


def test_high_only_changes_timing_and_flags_sooner_than_low():
    high = profile_for("High")
    low = profile_for("Low")
    assert high.yellow_sustain_frames < low.yellow_sustain_frames
    assert high.red_sustain_frames < low.red_sustain_frames

    def first_yellow(profile_name):
        _engine, history = _run_engine(profile_name)
        firsts = [levels.index("yellow") for levels in history.values() if "yellow" in levels]
        return min(firsts)

    assert first_yellow("high") < first_yellow("low")


def test_bad_sensitivity_name_fails_closed():
    for value in ("medium", "", "HIGHEST"):
        with pytest.raises(ValueError):
            profile_for(value)


def test_yellow_always_precedes_red_for_every_number():
    for profile_name in ("high", "low"):
        _engine, history = _run_engine(profile_name)
        for number, levels in history.items():
            if "red" in levels:
                assert "yellow" in levels
                assert levels.index("yellow") < levels.index("red"), (
                    profile_name,
                    number,
                )
            for previous, current in zip(levels, levels[1:]):
                if previous == "calm":
                    assert current != "red", "no calm->red jump"


def test_state_machine_escalates_through_yellow_and_resolves_when_settled():
    engine = MovementEngine(profile_for("high"))
    marker = Marker(number=1, x=0.5, y=0.5, energy=0.0)
    seen = []

    for _ in range(30):
        marker.step = 0.06  # sustained large movement
        seen.append(engine._advance_level(marker))
    assert seen[0] == 0  # starts calm
    assert 1 in seen and 2 in seen  # reaches yellow then red
    assert seen.index(1) < seen.index(2)  # yellow before red

    resolved = []
    for _ in range(60):
        marker.step = 0.0  # movement settles
        resolved.append(engine._advance_level(marker))
    assert resolved[-1] == 0  # returns all the way to calm
    assert resolved.index(1) < resolved.index(0)  # steps red->yellow->calm


# --- Recap: neutral, aggregate-only -----------------------------------------


def test_recap_is_uncertainty_first_and_not_punitive():
    engine, _history = _run_engine("low")
    recap = engine.recap()
    text = " ".join(recap.to_lines()).lower()

    assert "movement signals only" in text
    assert "not a measure of" in text
    assert "were not saved" in text or "not kept" in text
    for punitive in ("worst", "best", "rank", "ranked", "score", "grade", "punish"):
        assert punitive not in text

    assert recap.numbers_seen >= 1
    assert recap.peak_concurrent >= 1
    assert recap.sensitivity_name == "Low"


# --- Privacy boundary -------------------------------------------------------


def test_new_modules_have_no_frame_write_or_encode_api():
    for name in NEW_MODULES:
        source = (ROOT / "v2_runtime" / name).read_text(encoding="utf-8")
        for forbidden in ("imwrite", "VideoWriter", "imencode", "imread", "savefig"):
            assert forbidden not in source, (name, forbidden)


def test_state_payload_carries_positions_only_never_pixels():
    controller = SessionController(frame_interval=0.02)
    controller.start(source_kind="synthetic", camera_index=None, sensitivity="low")
    time.sleep(0.6)
    snapshot = controller.snapshot()
    controller.stop()

    assert snapshot["state"] == "running"
    assert snapshot["markers"], "expected at least one anonymous number"
    for marker in snapshot["markers"]:
        assert set(marker) == {"number", "x", "y", "level"}
        assert 0.0 <= marker["x"] <= 1.0 and 0.0 <= marker["y"] <= 1.0
        assert marker["level"] in {"calm", "yellow", "red"}


def test_serve_refuses_non_loopback_bind():
    for host in ("0.0.0.0", "192.168.0.10", "::1", "localhost"):
        with pytest.raises(PolicyViolation):
            serve(host=host, port=8471, open_browser=False)


def test_camera_source_requires_explicit_index():
    with pytest.raises(ValueError):
        build_source("camera", camera_index=None)
    with pytest.raises(ValueError):
        build_source("nonsense")


# --- Full teacher flow over the loopback service ----------------------------


def test_controller_hides_markers_immediately_for_privacy():
    controller = SessionController(frame_interval=0.02)
    controller.start(source_kind="synthetic", camera_index=None, sensitivity="high")
    time.sleep(0.5)
    assert controller.snapshot()["count"] >= 1

    controller.set_hidden(True)
    hidden = controller.snapshot()
    assert hidden["hidden"] is True
    assert hidden["markers"] == []
    assert hidden["overall"] == "hidden"
    controller.stop()


def test_full_dashboard_flow_start_live_stop_recap_delete():
    from fastapi.testclient import TestClient

    controller = SessionController(frame_interval=0.02)
    client = TestClient(create_app(controller))

    assert client.get("/health").json()["ok"] is True
    assert client.get("/", follow_redirects=False).status_code == 200

    started = client.post(
        "/start",
        data={"sensitivity": "low", "source": "synthetic"},
        follow_redirects=False,
    )
    assert started.status_code == 303 and started.headers["location"] == "/live"

    time.sleep(0.8)
    state = client.get("/state").json()
    assert state["state"] == "running"
    assert state["count"] >= 1

    headers = client.get("/live").headers
    assert headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in headers["content-security-policy"]
    assert headers["cache-control"] == "no-store"

    stopped = client.post("/stop", follow_redirects=False)
    assert stopped.status_code == 303 and stopped.headers["location"] == "/recap"

    recap = client.get("/recap").text
    assert "movement signals only" in recap
    assert "no ranking" in recap

    deleted = client.post("/delete", follow_redirects=False)
    assert deleted.status_code == 303
    assert controller.state == "idle"
    assert controller.recap_lines() == []
