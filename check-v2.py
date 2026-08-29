#!/usr/bin/env python3
"""Stage-gated acceptance runner for the accepted Classroom Mirror V2 path."""

import argparse
import ast
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parent
T1_SUITE = ROOT / "v2_tests" / "test_windows_runtime.py"
STRICT_PLUGIN = "v2_tests.strict_acceptance"
REQUIRED_T1_TESTS = {
    "V2-T1-01": "test_preflight_runs_without_admin_or_installing",
    "V2-T1-02": "test_camera_inventory_can_select_non_default_device",
    "V2-T1-03": "test_missing_or_denied_camera_fails_clearly",
    "V2-T1-04": "test_selected_camera_reads_frames_in_memory_and_releases",
    "V2-T1-05": "test_camera_smoke_writes_no_frame_image_or_video",
    "V2-T1-06": "test_service_refuses_non_loopback_bind",
    "V2-T1-07": "test_runtime_completes_with_outbound_network_blocked",
    "V2-T1-08": "test_run_bat_smoke_uses_selected_camera_and_exits",
    "V2-T1-09": "test_runtime_file_writes_are_allowlisted",
    "V2-T1-10": "test_t1_result_rejects_skips_and_empty_collection",
}


def run_t0() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromName(
        "v2_tests.test_t0_delta"
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def inspect_t1_acceptance_tests(suite_path: Path) -> tuple[set[str], set[str]]:
    """Return required IDs present/missing by exact acceptance test name."""
    if not suite_path.is_file():
        return set(), set(REQUIRED_T1_TESTS)
    try:
        tree = ast.parse(suite_path.read_text(encoding="utf-8"), filename=str(suite_path))
    except (OSError, SyntaxError, UnicodeError):
        return set(), set(REQUIRED_T1_TESTS)

    function_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    present = {
        criterion
        for criterion, test_name in REQUIRED_T1_TESTS.items()
        if test_name in function_names
    }
    return present, set(REQUIRED_T1_TESTS) - present


def run_pytest_strict(suite_path: Path, camera_index: int | None = None) -> int:
    """Run pytest with skip/xfail/xpass converted into failure."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        STRICT_PLUGIN,
        str(suite_path),
    ]
    if camera_index is not None:
        command.extend(("--camera-index", str(camera_index)))
        env["CLASSROOM_MIRROR_TEST_CAMERA_INDEX"] = str(camera_index)
    return subprocess.call(command, cwd=ROOT, env=env)


def run_t1(camera_index: int | None) -> int:
    present, missing = inspect_t1_acceptance_tests(T1_SUITE)
    if missing:
        print("T1 acceptance suite is incomplete; missing required criteria:")
        for criterion in sorted(missing):
            print(f"- {criterion}: {REQUIRED_T1_TESTS[criterion]}")
        return 1
    if not present:
        print("T1 acceptance suite collected no required criteria.")
        return 1
    if camera_index is None or camera_index < 0:
        print("T1 requires --camera-index with an enumerated USB camera index.")
        return 2

    return run_pytest_strict(T1_SUITE, camera_index=camera_index)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a stage of the accepted Classroom Mirror V2 contract."
    )
    parser.add_argument("--stage", choices=("t0", "t1"), required=True)
    parser.add_argument("--camera-index", type=int)
    args = parser.parse_args()

    if args.stage == "t0":
        return run_t0()
    return run_t1(args.camera_index)


if __name__ == "__main__":
    raise SystemExit(main())
