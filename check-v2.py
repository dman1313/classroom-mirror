#!/usr/bin/env python3
"""Stage-gated acceptance runner for the accepted Classroom Mirror V2 path."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parent
T1_SUITE = ROOT / "v2_tests" / "test_windows_runtime.py"


def run_t0() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromName(
        "v2_tests.test_t0_delta"
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def run_t1(camera_index: int | None) -> int:
    if camera_index is None or camera_index < 0:
        print("T1 requires --camera-index with an enumerated USB camera index.")
        return 2
    if not T1_SUITE.is_file():
        print(
            "T1 acceptance suite is not implemented: "
            "v2_tests/test_windows_runtime.py is missing."
        )
        return 1

    env = os.environ.copy()
    env["CLASSROOM_MIRROR_TEST_CAMERA_INDEX"] = str(camera_index)
    return subprocess.call(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            str(T1_SUITE),
            "--camera-index",
            str(camera_index),
        ],
        cwd=ROOT,
        env=env,
    )


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
