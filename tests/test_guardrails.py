"""Guardrail criteria 1-8. These run first and outrank everything."""
import importlib.metadata
import os
import re

import pytest

from app.db import Database, EXPECTED_SCHEMA, DATA_DIR
from app.validate import validate_lims, validate_class_code
from tests.criteria import evidence
from tests.fixtures import ZONE, build_mode1_db, build_mode2_db, stream_class

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", ".venv", ".pytest_cache", "__pycache__"}
MEDIA_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp",
             ".mp4", ".avi", ".mov", ".mkv", ".heic", ".tiff"}


def _tree(root):
    found = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            found.add(os.path.relpath(os.path.join(dirpath, f), root))
    return found


def _make_test_video(path, seconds=3, fps=25):
    import cv2
    import numpy as np
    w, h = 320, 240
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for i in range(seconds * fps):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        x = (i * 4) % (w - 40)
        frame[100:180, x:x + 40] = 255
        writer.write(frame)
    writer.release()


@pytest.mark.criterion(1)
def test_pipeline_writes_no_frames_anywhere(tmp_path):
    from app.camera import process_video, persist_results
    from app.detector import PoseDetector
    from app.session import Mode2Engine

    video = tmp_path / "synthetic.mp4"
    _make_test_video(video)

    before_repo = _tree(ROOT)
    db = Database(data_dir=str(tmp_path / "data"))
    sid = db.start_session("mode2", "none", "TEST-1")
    results = process_video(str(video), PoseDetector(), Mode2Engine())
    persist_results(db, sid, "mode2", results)
    db.close()

    new_in_repo = _tree(ROOT) - before_repo
    assert new_in_repo == set(), f"Pipeline created files in the project: {new_in_repo}"

    created = _tree(tmp_path / "data")
    bad = {f for f in created if os.path.splitext(f)[1].lower() in MEDIA_EXT
           or not f.startswith("mirror.sqlite")}
    assert bad == set(), f"Unexpected files in data dir: {bad}"
    assert DATA_DIR == os.path.join(ROOT, "data")
    evidence(1, "full pipeline on a generated 3s video created only "
                f"{sorted(created)} inside data/ — no image or video file anywhere")


@pytest.mark.criterion(2)
def test_no_face_recognition_capability(tmp_db):
    banned = {"face-recognition", "face_recognition", "dlib", "deepface",
              "insightface", "facenet-pytorch", "mtcnn", "retina-face",
              "retinaface", "opencv-contrib-python"}
    installed = {d.metadata["Name"].lower() for d in importlib.metadata.distributions()
                 if d.metadata["Name"]}
    overlap = installed & banned
    assert overlap == set(), f"Face-recognition-capable packages installed: {overlap}"

    for table, cols in tmp_db.live_schema().items():
        for col in cols:
            assert not re.search(r"embed|template|face|biometric", col, re.I), \
                f"Suspicious column {table}.{col}"
    evidence(2, f"{len(installed)} installed packages, none face-capable; "
                "schema has no embedding/template/biometric column")


BANNED_WORDS = re.compile(
    r"\b(emotion\w*|mood|attention|attentive|engag\w+|lazy|naughty|disruptive"
    r"|character|good|bad|focus\w*|misbehav\w*|off.task|on.task|score\w*)\b",
    re.I,
)


@pytest.mark.criterion(3)
def test_no_emotion_or_judgment_language(tmp_db):
    from app import reports
    build_mode1_db(tmp_db)
    sid_a, sid_b = build_mode2_db(tmp_db)
    rendered = (
        reports.mode1_report_html(tmp_db, "L-7")
        + reports.mode2_summary_html(tmp_db, sid_a)
        + reports.mode2_compare_html(tmp_db, sid_a, sid_b)
    )
    hits = sorted(set(m.group(0).lower() for m in BANNED_WORDS.finditer(rendered)))
    assert hits == [], f"Judgment/inference language found in reports: {hits}"

    for table, cols in tmp_db.live_schema().items():
        for col in cols:
            assert not re.search(r"emotion|attention|sentiment|score", col, re.I)
    evidence(3, "all three report types rendered and scanned: zero emotion/"
                "judgment terms; schema has nowhere to store such a thing")


@pytest.mark.criterion(4)
def test_names_cannot_enter(tmp_db):
    from app import pages
    for bad in ("Jean Dupont", "Marie", "a note about a child", "x" * 13):
        with pytest.raises(ValueError):
            validate_lims(bad)
    assert validate_lims("L-1042") == "L-1042"
    assert validate_class_code("6B") == "6B"

    with pytest.raises(ValueError):
        tmp_db.start_session("mode1", "baseline", "6B",
                             [{"lims": "Jean Dupont", "zone": ZONE, "consent": True}])

    html = pages.home_page([], []) + pages.setup_page() + pages.live_page(1)
    assert "<textarea" not in html.lower()
    for tag in re.findall(r"<input[^>]*>", html):
        assert "pattern=" in tag or "type='checkbox'" in tag, \
            f"Unrestricted input field: {tag}"
    evidence(4, "names like 'Jean Dupont' rejected at every entry point; "
                "no free-text field exists in any page")


@pytest.mark.criterion(5)
def test_local_only(tmp_db, loopback_only):
    import numpy as np
    from app import reports
    from app.detector import PoseDetector
    from app.session import Mode2Engine, run_offline
    from fastapi.testclient import TestClient
    from app.main import app

    frames, _ = stream_class()
    sid = tmp_db.start_session("mode2", "none", "TEST-1")
    for minute, bodies, raises, bucket in run_offline(frames, Mode2Engine()):
        tmp_db.add_mode2_minute(sid, minute, bodies, raises, bucket)
    reports.mode2_summary_html(tmp_db, sid)
    build_mode1_db(tmp_db)
    reports.mode1_report_html(tmp_db, "L-7")

    detector = PoseDetector()
    detector.detect(np.zeros((240, 320, 3), dtype=np.uint8))

    client = TestClient(app)
    assert client.get("/").status_code == 200

    assert loopback_only.attempts == []
    evidence(5, "full session, reports, model load and inference ran with "
                "non-loopback connections blocked: zero outbound attempts")


@pytest.mark.criterion(6)
def test_consent_gate(tmp_db):
    with pytest.raises(PermissionError):
        tmp_db.start_session("mode1", "baseline", "6B", [])
    with pytest.raises(PermissionError) as exc:
        tmp_db.start_session("mode1", "baseline", "6B",
                             [{"lims": "L-7", "zone": ZONE, "consent": False}])
    assert "onsent" in str(exc.value)

    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    r = client.post("/api/session/start", json={
        "mode": "mode1", "phase": "baseline", "class_code": "6B",
        "designations": [{"lims": "L-7", "zone": list(ZONE), "consent": False}],
    })
    assert r.status_code == 400
    assert "onsent" in r.json()["error"]
    evidence(6, "Mode 1 start without confirmed consent is refused at the "
                "database AND the web API, with a plain-English message")


@pytest.mark.criterion(7)
def test_mode2_aggregate_only(tmp_db):
    schema = tmp_db.live_schema()
    assert schema == EXPECTED_SCHEMA, \
        f"Schema drifted from the locked contract schema: {schema}"
    assert all("lims" not in c.lower() for c in schema["mode2_minutes"])
    evidence(7, "live schema matches the locked schema exactly; "
                f"mode2_minutes columns = {schema['mode2_minutes']} (no per-child column)")


@pytest.mark.criterion(8)
def test_erasure(tmp_db):
    sid = tmp_db.start_session("mode1", "baseline", "6B",
                               [{"lims": "L-9", "zone": ZONE, "consent": True}])
    tmp_db.add_mode1_minute(sid, "L-9", 0, 75.0, "low")
    tmp_db.add_mode1_event(sid, "L-9", 12.5)
    assert tmp_db.find_text_anywhere("L-9")
    removed = tmp_db.delete_lims("L-9")
    assert removed >= 3
    assert not tmp_db.find_text_anywhere("L-9")

    sid2 = tmp_db.start_session("mode2", "none", "6B")
    tmp_db.add_mode2_minute(sid2, 0, 20, 4, "medium")
    tmp_db.delete_session(sid2)
    assert tmp_db.get_session(sid2) is None
    assert tmp_db.mode2_data(sid2) == []
    evidence(8, "after delete, a full scan of every cell of every table "
                "finds no trace of the erased LIMS code or session")
