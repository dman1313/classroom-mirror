"""Teacher-only live preview: in-memory frames, no disk writes, guards intact."""

from __future__ import annotations

import http.client
import json
import socket
import threading
import time
from pathlib import Path


import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]

# JPEG start-of-image / end-of-image markers.
JPEG_SOI = b"\xff\xd8"
JPEG_EOI = b"\xff\xd9"


class _FakeCapture:
    """Minimal stand-in for cv2.VideoCapture that never touches hardware/disk."""

    def __init__(self, index, frame):
        self.index = index
        self._frame = frame
        self.released = False

    def isOpened(self):
        return True

    def read(self):
        return True, self._frame.copy()

    def release(self):
        self.released = True


def _install_fake_camera(monkeypatch, frame):
    import cv2

    from v2_app import capture as capture_mod

    monkeypatch.setattr(cv2, "VideoCapture", lambda index: _FakeCapture(index, frame))
    # Skip real face detection; the preview must work regardless of detections.
    monkeypatch.setattr(capture_mod, "detect_faces_bgr", lambda frame: [])


def _wait_for(predicate, timeout=3.0, interval=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    return predicate()


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _BackgroundServer:
    """Run the real ASGI app on loopback in a thread (mirrors production)."""

    def __init__(self, app, port):
        import uvicorn

        self.server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
        )
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self):
        self.thread.start()
        if not _wait_for(lambda: self.server.started, timeout=10):
            raise RuntimeError("uvicorn did not start")
        return self

    def __exit__(self, *exc):
        self.server.should_exit = True
        self.thread.join(timeout=5)


def test_capture_publishes_inmemory_jpeg_and_clears_on_stop(monkeypatch):
    from v2_app.capture import CaptureLoop

    frame = np.full((48, 64, 3), 127, dtype=np.uint8)
    _install_fake_camera(monkeypatch, frame)

    class _StubEngine:
        def ingest(self, *args, **kwargs):
            pass

    loop = CaptureLoop(_StubEngine(), camera_index=0)
    assert loop.latest_jpeg() is None
    loop.start()
    try:
        jpeg = _wait_for(loop.latest_jpeg)
        assert jpeg is not None, "capture loop never published an in-memory frame"
        assert jpeg.startswith(JPEG_SOI) and jpeg.endswith(JPEG_EOI)
        assert loop.error is None
    finally:
        loop.stop()

    # Nothing lingers in RAM after stop, and nothing was persisted.
    assert loop.latest_jpeg() is None


def test_capture_and_server_have_no_frame_write_apis():
    forbidden = ("imwrite", "videowriter")
    for name in ("capture.py", "server.py"):
        source = (ROOT / "v2_app" / name).read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in source, f"{name} must not use frame-write API {token!r}"
        # In-RAM JPEG encoding for streaming is allowed and expected in capture.
        if name == "capture.py":
            assert "imencode" in source


def test_preview_endpoint_requires_running_session(monkeypatch, tmp_path):
    monkeypatch.setenv("CLASSROOM_MIRROR_DATA_DIR", str(tmp_path / "data"))
    from fastapi.testclient import TestClient

    from v2_app.server import create_app

    client = TestClient(create_app())
    r = client.get("/api/preview")
    assert r.status_code == 400
    assert r.json()["error"] == "not running"


def test_preview_endpoint_streams_inmemory_jpeg_when_running(monkeypatch, tmp_path):
    monkeypatch.setenv("CLASSROOM_MIRROR_DATA_DIR", str(tmp_path / "data"))
    frame = np.full((48, 64, 3), 200, dtype=np.uint8)
    _install_fake_camera(monkeypatch, frame)

    from v2_app.server import create_app

    port = _free_port()
    with _BackgroundServer(create_app(), port):
        started = _post(port, "/api/start", {"camera_index": 0, "sensitivity": "low"})
        assert started.status == 200

        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=8)
        try:
            conn.request("GET", "/api/preview")
            resp = conn.getresponse()
            assert resp.status == 200
            assert "multipart/x-mixed-replace" in resp.getheader("Content-Type")
            assert resp.getheader("Cache-Control") == "no-store"
            buffered = b""
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline and len(buffered) < 1_000_000:
                chunk = resp.read(4096)
                if not chunk:
                    break
                buffered += chunk
                if (
                    b"Content-Type: image/jpeg" in buffered
                    and JPEG_SOI in buffered
                    and JPEG_EOI in buffered
                ):
                    break
            assert b"Content-Type: image/jpeg" in buffered
            assert JPEG_SOI in buffered and JPEG_EOI in buffered
        finally:
            conn.close()

        stopped = _post(port, "/api/stop", {})
        assert stopped.status == 200


def _post(port, path, payload):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=8)
    body = json.dumps(payload)
    conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    resp.read()
    conn.close()
    return resp


def test_schema_guard_skips_sqlite_internal_but_blocks_forbidden(tmp_path, monkeypatch):
    monkeypatch.setenv("CLASSROOM_MIRROR_DATA_DIR", str(tmp_path / "data"))
    from v2_app.store import Store

    store = Store()
    # AUTOINCREMENT creates sqlite_sequence (with a column named "name"); the
    # guard must ignore it so the dashboard can start.
    store._conn.execute(
        "INSERT INTO sessions(started_at, sensitivity) VALUES ('t', 'low')"
    )
    store._conn.commit()
    store._assert_schema()  # must not raise on sqlite_sequence
    tables = {row[0] for row in store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "sqlite_sequence" in tables

    # A real forbidden column in an application table is still rejected.
    store._conn.execute("CREATE TABLE leak (id INTEGER PRIMARY KEY, name TEXT)")
    store._conn.commit()
    with pytest.raises(RuntimeError, match="forbidden column name"):
        store._assert_schema()
