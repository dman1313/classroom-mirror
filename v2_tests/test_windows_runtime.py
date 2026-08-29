"""T1 Windows runtime acceptance tests that do not require a real camera."""

from __future__ import annotations

import importlib.util
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
    assert present == {
        "V2-T1-01",
        "V2-T1-06",
        "V2-T1-07",
        "V2-T1-09",
        "V2-T1-10",
    }
    assert missing == {
        "V2-T1-02",
        "V2-T1-03",
        "V2-T1-04",
        "V2-T1-05",
        "V2-T1-08",
    }


def test_run_bat_foundation_fails_closed_until_camera_increment():
    source = (ROOT / "run.bat").read_text(encoding="utf-8").lower()
    for argument in ("--smoke-test", "--camera-index", "--seconds"):
        assert argument in source
    assert "v2_runtime.launcher" in source
    assert "exit /b %result%" in source
