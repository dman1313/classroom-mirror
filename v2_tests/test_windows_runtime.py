"""T1 Windows runtime acceptance tests that do not require a real camera."""

from __future__ import annotations

import importlib.util
import builtins
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import re
from unittest.mock import patch

import pytest

from v2_runtime.policy import (
    PolicyViolation,
    RuntimeFilePolicy,
    RuntimeNetworkPolicy,
    validate_bind_host,
)


ROOT = Path(__file__).resolve().parents[1]


class FakeFrame:
    size = 12


class FakeCapture:
    def __init__(self, index, *, opened=True, frames=(), backend="FAKE"):
        self.index = index
        self._opened = opened
        self._frames = list(frames)
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


class FakeCaptureFactory:
    def __init__(self, cameras=None, error=None):
        self.cameras = cameras or {}
        self.error = error
        self.opened_indexes = []
        self.instances = []

    def __call__(self, index):
        self.opened_indexes.append(index)
        if self.error is not None:
            raise self.error
        capture = FakeCapture(index, **self.cameras.get(index, {"opened": False}))
        self.instances.append(capture)
        return capture


def _snapshot_files(*roots):
    return {
        path.resolve()
        for root in roots
        for path in Path(root).rglob("*")
        if path.is_file()
    }


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


def test_camera_inventory_can_select_non_default_device():
    """V2-T1-02: rows are safe and capture never substitutes index zero."""
    from v2_runtime.camera import inventory_cameras, inventory_display_rows, smoke_camera

    inventory_factory = FakeCaptureFactory(
        {
            0: {"opened": True, "backend": "BUILT-IN"},
            1: {"opened": False},
            2: {
                "opened": True,
                "backend": r"MSMF C:\\Users\\Teacher\\serial-ABC123",
            },
        }
    )
    cameras = inventory_cameras(max_index=2, capture_factory=inventory_factory)

    assert [camera.index for camera in cameras] == [0, 2]
    assert inventory_display_rows(cameras) == (
        "Camera 1 (index 0)",
        "Camera 2 (index 2)",
    )
    rows = " ".join(inventory_display_rows(cameras)).lower()
    assert "serial" not in rows
    assert "users" not in rows
    assert "teacher" not in rows
    assert all(capture.released for capture in inventory_factory.instances)

    selected_factory = FakeCaptureFactory(
        {2: {"opened": True, "frames": [(True, FakeFrame())], "backend": "MSMF"}}
    )
    times = iter((0.0, 0.0, 0.2))
    result = smoke_camera(
        2,
        seconds=0.1,
        capture_factory=selected_factory,
        clock=lambda: next(times),
        sleeper=lambda _: None,
    )
    assert result.camera_index == 2
    assert selected_factory.opened_indexes == [2]


@pytest.mark.parametrize(
    ("factory", "message"),
    (
        (
            FakeCaptureFactory(error=PermissionError("camera access denied")),
            r"permission denied.*ms-settings:privacy-webcam",
        ),
        (
            FakeCaptureFactory(error=BlockingIOError("device is busy")),
            r"busy.*another app",
        ),
        (
            FakeCaptureFactory({4: {"opened": False}}),
            r"not available.*plugged in",
        ),
    ),
)
def test_missing_or_denied_camera_fails_clearly(factory, message):
    """V2-T1-03: absent, busy, and permission failures are distinguishable."""
    from v2_runtime.camera import CameraUnavailable, smoke_camera

    with pytest.raises(CameraUnavailable, match=message):
        smoke_camera(4, seconds=0.1, capture_factory=factory)
    assert factory.opened_indexes == [4]
    assert all(capture.released for capture in factory.instances)


def test_selected_camera_reads_frames_in_memory_and_releases():
    """V2-T1-04: bounded frames stay in memory and every capture is released."""
    from v2_runtime.camera import CameraUnavailable, smoke_camera

    success = FakeCaptureFactory(
        {3: {"opened": True, "frames": [(True, FakeFrame())], "backend": "MSMF"}}
    )
    times = iter((0.0, 0.0, 0.2))
    result = smoke_camera(
        3,
        seconds=0.1,
        capture_factory=success,
        clock=lambda: next(times),
        sleeper=lambda _: None,
    )
    assert result.frame_count == 1
    assert success.instances[0].released

    failure = FakeCaptureFactory({3: {"opened": True, "frames": []}})
    times = iter((0.0, 0.0))
    with pytest.raises(CameraUnavailable, match="stopped sending frames"):
        smoke_camera(
            3,
            seconds=0.1,
            capture_factory=failure,
            clock=lambda: next(times),
            sleeper=lambda _: None,
        )
    assert failure.instances[0].released


def test_camera_smoke_writes_no_frame_image_or_video(tmp_path, monkeypatch):
    """V2-T1-05: smoke performs no media or other filesystem write."""
    from v2_runtime.camera import smoke_camera

    repo = tmp_path / "repo"
    cwd = tmp_path / "cwd"
    user_data = tmp_path / "LocalAppData"
    run_scratch = tmp_path / "run-scratch"
    for root in (repo, cwd, user_data, run_scratch):
        root.mkdir()
    before = _snapshot_files(repo, cwd, user_data, run_scratch)
    write_calls = []
    original_open = builtins.open

    def guarded_open(file, mode="r", *args, **kwargs):
        if any(flag in mode for flag in "wax+"):
            write_calls.append((Path(file), mode))
        return original_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("LOCALAPPDATA", str(user_data))
    monkeypatch.setenv("PAPERCLIP_RUN_SCRATCH_DIR", str(run_scratch))
    factory = FakeCaptureFactory(
        {2: {"opened": True, "frames": [(True, FakeFrame())]}}
    )
    times = iter((0.0, 0.0, 0.2))

    result = smoke_camera(
        2,
        seconds=0.1,
        capture_factory=factory,
        clock=lambda: next(times),
        sleeper=lambda _: None,
    )

    assert result.frame_count == 1
    assert write_calls == []
    assert _snapshot_files(repo, cwd, user_data, run_scratch) == before
    assert factory.instances[0].released


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
        "state/identities.bin",
        "logs/runtime.log",
        "config/runtime.json",
        "config/template.key",
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


def test_run_bat_foundation_fails_closed_until_camera_increment():
    source = (ROOT / "run.bat").read_text(encoding="utf-8").lower()
    for argument in ("--smoke-test", "--camera-index", "--seconds"):
        assert argument in source
    assert "v2_runtime.launcher" in source
    assert "exit /b %result%" in source


def test_run_bat_smoke_uses_selected_camera_and_exits():
    """V2-T1-08: smoke captures, health-checks loopback, and shuts down."""
    from v2_runtime.camera import CameraSmokeResult, CameraUnavailable
    from v2_runtime import launcher

    smoke_calls = []
    health_calls = []

    def fake_smoke(index, *, seconds):
        smoke_calls.append((index, seconds))
        return CameraSmokeResult(index, "MSMF", 4, seconds)

    def fake_health(index, *, host):
        health_calls.append((index, host))
        return {
            "ok": True,
            "camera_index": index,
            "host": host,
            "stopped": True,
            "outbound_attempts": 0,
        }

    output = StringIO()
    with patch.object(launcher, "smoke_camera", fake_smoke), patch.object(
        launcher, "run_local_health_check", fake_health
    ), redirect_stdout(output), redirect_stderr(output):
        result = launcher.main(
            ["--smoke-test", "--camera-index", "3", "--seconds", "0.25"]
        )

    assert result == 0
    assert smoke_calls == [(3, 0.25)]
    assert health_calls == [(3, "127.0.0.1")]
    assert "selected camera index: 3" in output.getvalue().lower()
    assert "local health: pass" in output.getvalue().lower()
    assert "service stopped: yes" in output.getvalue().lower()

    with patch.object(
        launcher,
        "smoke_camera",
        side_effect=CameraUnavailable("Camera 3 is busy in another app."),
    ), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        assert launcher.main(
            ["--smoke-test", "--camera-index", "3", "--seconds", "0.25"]
        ) != 0

    source = (ROOT / "run.bat").read_text(encoding="utf-8").lower()
    assert "--smoke-test" in source
    assert "v2_runtime.launcher" in source


def test_teacher_capture_ui_is_private_controllable_and_has_no_identity_fields():
    from v2_runtime.teacher_ui import TeacherCaptureSession, render_teacher_page

    factory = FakeCaptureFactory(
        {
            2: {
                "opened": True,
                "frames": [(True, FakeFrame()), (True, FakeFrame())],
                "backend": "MSMF",
            }
        }
    )
    session = TeacherCaptureSession(capture_factory=factory)
    session.set_inventory_indexes([2])
    session.select_camera(2)
    preview = session.read_setup_preview()
    assert preview is not None
    assert session.preview_frame is preview
    session.start()
    assert session.active
    session.hide()
    assert not session.teacher_ui_visible
    session.show()
    assert session.teacher_ui_visible
    session.stop()
    assert not session.active
    assert session.preview_frame is None
    assert factory.opened_indexes == [2]
    assert factory.instances[0].released

    html = render_teacher_page().lower()
    for control in ("camera-select", "setup-preview", "start-session", "stop-session", "hide-ui", "show-ui"):
        assert control in html
    assert "student" not in html
    assert "name=" not in html
