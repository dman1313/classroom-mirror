"""T1 Windows runtime acceptance tests.

Tests marked ``camera`` require an explicitly selected real USB webcam (see
``camera_index`` in ``v2_tests/strict_acceptance.py``) and are the genuine
hardware proof for the acceptance IDs that need it; every other test uses
fakes and temporary directories only, per the T1 focused development loop in
``V2-DELTA.md``.
"""

from __future__ import annotations

from contextlib import redirect_stderr
import importlib.util
from io import StringIO
from pathlib import Path
import re

import pytest

from v2_runtime.policy import (
    PolicyViolation,
    RuntimeFilePolicy,
    RuntimeNetworkPolicy,
    validate_bind_host,
)


ROOT = Path(__file__).resolve().parents[1]


def _list_files(root: Path) -> set[str]:
    """A filename-only snapshot; used to prove a directory tree is untouched."""
    if not root.exists():
        return set()
    return {
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }


class _FakeCapture:
    def __init__(self, opened: bool = False, frames=None, backend: str = "USB"):
        self._opened = opened
        self._frames = list(frames or ())
        self._backend = backend
        self.released = False

    def isOpened(self):
        return self._opened

    def read(self):
        if not self._frames:
            return False, None
        return self._frames.pop(0)

    def getBackendName(self):
        return self._backend

    def release(self):
        self.released = True


class _FakeCaptureFactory:
    """A capture_factory that also simulates OS-level open failures."""

    def __init__(self, cameras: dict | None = None, raises: dict | None = None):
        self.cameras = cameras or {}
        self.raises = raises or {}
        self.opened_indexes: list[int] = []
        self.instances: list[_FakeCapture] = []

    def __call__(self, index: int) -> _FakeCapture:
        self.opened_indexes.append(index)
        if index in self.raises:
            raise self.raises[index]
        capture = _FakeCapture(**self.cameras.get(index, {}))
        self.instances.append(capture)
        return capture


def _load_v2_runner():
    spec = importlib.util.spec_from_file_location("check_v2", ROOT / "check-v2.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_preflight_runs_without_admin_or_installing():
    """V2-T1-01: CheckOnly is read-only and reports every required fact."""
    source = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert re.search(r"param\s*\([^)]*\[switch\]\s*\$CheckOnly", source, re.I | re.S)
    for label in (
        "Windows version:",
        "Architecture:",
        "Python/runtime:",
        "Execution policy:",
        "Per-user data:",
        "Camera availability:",
        "Administrator:",
    ):
        assert label in source

    forbidden = (
        r"Start-Process[^\r\n]+RunAs",
        r"Set-ExecutionPolicy",
        r"\bpip(?:\.exe)?\s+install\b",
        r"\bwinget\b",
        r"\bchoco\b",
        r"\bNew-Item\b",
        r"\bSet-Content\b",
        r"\bAdd-Content\b",
        r"\bOut-File\b",
    )
    for pattern in forbidden:
        assert re.search(pattern, source, re.I) is None, pattern


def test_service_refuses_non_loopback_bind():
    """V2-T1-06: the service accepts exactly IPv4 127.0.0.1."""
    assert validate_bind_host("127.0.0.1") == "127.0.0.1"

    for host in (
        "0.0.0.0",
        "192.168.1.20",
        "10.0.0.4",
        "::",
        "::1",
        "localhost",
        "127.0.0.2",
        "example.invalid",
    ):
        with pytest.raises(PolicyViolation, match="127.0.0.1"):
            validate_bind_host(host)


def test_runtime_completes_with_outbound_network_blocked():
    """V2-T1-07: local health can run while outbound calls fail closed."""
    connector_calls = []

    def connector(address, timeout=None):
        connector_calls.append((address, timeout))
        return "local-health-connection"

    policy = RuntimeNetworkPolicy(connector=connector)
    result = policy.connect(("127.0.0.1", 8470), timeout=1.0)

    assert result == "local-health-connection"
    assert policy.outbound_attempts == ()
    assert connector_calls == [(('127.0.0.1', 8470), 1.0)]

    for address in (("8.8.8.8", 53), ("example.invalid", 443), ("::", 8470)):
        with pytest.raises(PolicyViolation, match="outbound"):
            policy.connect(address, timeout=1.0)

    assert connector_calls == [(('127.0.0.1', 8470), 1.0)]
    assert policy.outbound_attempts == (
        ("8.8.8.8", 53),
        ("example.invalid", 443),
        ("::", 8470),
    )


def test_runtime_file_writes_are_allowlisted(tmp_path):
    """V2-T1-09: only documented non-media files can be written."""
    local_app_data = tmp_path / "LocalAppData"
    policy = RuntimeFilePolicy(local_app_data=local_app_data)

    expected = {
        "state/classroom-mirror.sqlite3",
        "state/classroom-mirror.sqlite3-wal",
        "state/classroom-mirror.sqlite3-shm",
        "logs/runtime.log",
        "config/runtime.json",
    }
    documentation = (ROOT / "WINDOWS-RUNTIME-POLICY.md").read_text(encoding="utf-8")
    for relative in expected:
        resolved = policy.resolve_write(relative)
        assert resolved.is_relative_to(local_app_data.resolve())
        assert resolved.is_relative_to(policy.root)
        assert relative in documentation

    with policy.open_text("logs/runtime.log", mode="a") as stream:
        stream.write("runtime start\n")
    with policy.open_text("config/runtime.json", mode="w") as stream:
        stream.write("{}\n")
    written = {
        path.relative_to(policy.root).as_posix()
        for path in policy.root.rglob("*")
        if path.is_file()
    }
    assert written == {"logs/runtime.log", "config/runtime.json"}
    with pytest.raises(PolicyViolation):
        policy.open_text("state/classroom-mirror.sqlite3", mode="w")

    outside = tmp_path / "outside"
    outside.mkdir()
    (policy.root / "state").symlink_to(outside, target_is_directory=True)
    with pytest.raises(PolicyViolation, match="escaped"):
        policy.resolve_write("state/classroom-mirror.sqlite3")

    for disallowed in (
        "../escape.log",
        "state/frame.jpg",
        "state/session.mp4",
        "state/crop.png",
        "state/audio.wav",
        "notes.txt",
        str(ROOT / "runtime.log"),
    ):
        with pytest.raises(PolicyViolation):
            policy.resolve_write(disallowed)


def test_t1_result_rejects_skips_and_empty_collection(tmp_path):
    """V2-T1-10: missing criteria and every non-pass outcome are failures."""
    runner = _load_v2_runner()

    def complete_suite(first_test_body):
        lines = ["import pytest", ""]
        for index, test_name in enumerate(runner.REQUIRED_T1_TESTS.values()):
            lines.append(f"def {test_name}():")
            lines.append(f"    {first_test_body if index == 0 else 'assert True'}")
            lines.append("")
        return "\n".join(lines)

    missing_suite = tmp_path / "test_missing.py"
    missing_suite.write_text(
        "def test_preflight_runs_without_admin_or_installing(): pass\n",
        encoding="utf-8",
    )
    runner.T1_SUITE = missing_suite
    assert runner.run_t1(camera_index=0) != 0

    empty_suite = tmp_path / "test_empty.py"
    empty_suite.write_text(
        "if False:\n    " + complete_suite("assert True").replace("\n", "\n    "),
        encoding="utf-8",
    )
    runner.T1_SUITE = empty_suite
    assert runner.run_t1(camera_index=0) != 0

    cases = {
        "skip": "pytest.skip('not proof')",
        "xfail": "pytest.xfail('not proof')",
        "failure": "assert False",
        "pass": "assert True",
    }
    outcomes = {}
    for name, first_test_body in cases.items():
        suite = tmp_path / f"test_{name}.py"
        suite.write_text(complete_suite(first_test_body), encoding="utf-8")
        runner.T1_SUITE = suite
        outcomes[name] = runner.run_t1(camera_index=0)

    assert outcomes == {"skip": 1, "xfail": 1, "failure": 1, "pass": 0}

    present, missing = runner.inspect_t1_acceptance_tests(Path(__file__))
    assert present == set(runner.REQUIRED_T1_TESTS)
    assert missing == set()


def test_camera_inventory_can_select_non_default_device(monkeypatch, tmp_path):
    """V2-T1-02: inventory rows are stable and the launcher opens the
    requested index, never a hardcoded camera 0."""
    from v2_runtime import camera, launcher

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    inventory_factory = _FakeCaptureFactory(
        {0: {"opened": True, "backend": "BUILT-IN"}, 4: {"opened": True, "backend": "USB"}}
    )
    inventory = camera.inventory_cameras(max_index=4, capture_factory=inventory_factory)
    assert [row.index for row in inventory] == [0, 4]
    assert [row.backend for row in inventory] == ["BUILT-IN", "USB"]

    smoke_factory = _FakeCaptureFactory(
        {4: {"opened": True, "backend": "USB", "frames": [(True, object())] * 40}}
    )
    monkeypatch.setattr(camera, "_opencv_capture", smoke_factory)
    monkeypatch.setattr(launcher, "_run_bounded_service", lambda *a, **k: {"ok": True})

    result = launcher.main(["--smoke-test", "--camera-index", "4", "--seconds", "0.05"])

    assert result == 0
    assert smoke_factory.opened_indexes == [4]


def test_missing_or_denied_camera_fails_clearly(monkeypatch, tmp_path):
    """V2-T1-03: absent, busy, and OS-denied cameras get distinct diagnostics,
    with ms-settings:privacy-webcam guidance shown only for denial."""
    from v2_runtime import camera, launcher

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    absent_factory = _FakeCaptureFactory({})
    monkeypatch.setattr(camera, "_opencv_capture", absent_factory)
    output = StringIO()
    with redirect_stderr(output):
        result = launcher.main(["--smoke-test", "--camera-index", "3", "--seconds", "0.05"])
    assert result == launcher.EXIT_CAMERA_ABSENT
    assert "was not found" in output.getvalue()
    assert "ms-settings:privacy-webcam" not in output.getvalue()

    busy_factory = _FakeCaptureFactory(raises={3: OSError("device busy")})
    monkeypatch.setattr(camera, "_opencv_capture", busy_factory)
    output = StringIO()
    with redirect_stderr(output):
        result = launcher.main(["--smoke-test", "--camera-index", "3", "--seconds", "0.05"])
    assert result == launcher.EXIT_CAMERA_BUSY
    assert "in use by another application" in output.getvalue()
    assert "ms-settings:privacy-webcam" not in output.getvalue()

    denied_factory = _FakeCaptureFactory(raises={3: PermissionError("camera access denied")})
    monkeypatch.setattr(camera, "_opencv_capture", denied_factory)
    output = StringIO()
    with redirect_stderr(output):
        result = launcher.main(["--smoke-test", "--camera-index", "3", "--seconds", "0.05"])
    assert result == launcher.EXIT_CAMERA_DENIED
    assert "ms-settings:privacy-webcam" in output.getvalue()


@pytest.mark.camera
def test_selected_camera_reads_frames_in_memory_and_releases(camera_index):
    """V2-T1-04: the real selected USB camera reads frames and is released."""
    import cv2

    from v2_runtime.camera import smoke_camera

    result = smoke_camera(camera_index, seconds=1.0)

    assert result.camera_index == camera_index
    assert result.frame_count > 0
    assert result.backend

    reopened = cv2.VideoCapture(camera_index)
    try:
        assert reopened.isOpened(), "camera was not released by the prior smoke"
    finally:
        reopened.release()


@pytest.mark.camera
def test_camera_smoke_writes_no_frame_image_or_video(camera_index, tmp_path, monkeypatch):
    """V2-T1-05: a real-camera smoke leaves no new file anywhere watched."""
    from v2_runtime.camera import smoke_camera

    local_app_data = tmp_path / "LocalAppData"
    local_app_data.mkdir()
    work_dir = tmp_path / "cwd"
    work_dir.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.chdir(work_dir)

    before = {
        "repo": _list_files(ROOT),
        "local_app_data": _list_files(local_app_data),
        "cwd": _list_files(work_dir),
    }

    result = smoke_camera(camera_index, seconds=1.0)
    assert result.frame_count > 0

    after = {
        "repo": _list_files(ROOT),
        "local_app_data": _list_files(local_app_data),
        "cwd": _list_files(work_dir),
    }
    assert after == before

    source = (ROOT / "v2_runtime" / "camera.py").read_text(encoding="utf-8")
    for forbidden in ("imwrite", "VideoWriter", "imencode"):
        assert forbidden not in source


@pytest.mark.camera
def test_run_bat_smoke_uses_selected_camera_and_exits(camera_index, tmp_path, monkeypatch):
    """V2-T1-08: run.bat's underlying launcher uses the selected real camera,
    starts the loopback service, reports health, and returns nonzero on
    failure."""
    from v2_runtime import launcher

    source = (ROOT / "run.bat").read_text(encoding="utf-8")
    assert "v2_runtime.launcher" in source
    assert "%*" in source

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    ok = launcher.main(["--smoke-test", "--camera-index", str(camera_index), "--seconds", "1"])
    assert ok == 0

    def _raise_service_failure(*_args, **_kwargs):
        raise RuntimeError("loopback service did not start within the bounded window")

    monkeypatch.setattr(launcher, "_run_bounded_service", _raise_service_failure)
    failing = launcher.main(["--smoke-test", "--camera-index", str(camera_index), "--seconds", "1"])
    assert failing == launcher.EXIT_SERVICE_FAILED
    assert failing != 0


def test_run_bat_forwards_arguments_and_propagates_exit_code():
    source = (ROOT / "run.bat").read_text(encoding="utf-8").lower()
    for argument in ("--smoke-test", "--camera-index", "--seconds"):
        assert argument in source
    assert "v2_runtime.launcher" in source
    assert "exit /b %result%" in source
