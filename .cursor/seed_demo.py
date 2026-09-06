#!/usr/bin/env python3
"""Populate the app database with demo sessions so the dashboard and reports
have something to show WITHOUT a camera.

Data is produced by driving the app's REAL analytics engines over the
repository's own synthetic keypoint fixtures (keypoints -> engine -> DB ->
report). No camera and no real children's data are involved, per CONTRACT.md.

Usage (from the repo root):
    ./.venv/bin/python .cursor/seed_demo.py

Run with --reset to erase existing demo rows for L-7 first, so re-running does
not keep stacking baseline/strategy sessions.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import Database
from app.session import Mode1Engine, Mode2Engine, run_offline
from app.camera import persist_results
from tests.fixtures import ZONE, stream_class, stream_three_raises, stream_away

LIMS = "L-7"


def seed(reset: bool) -> None:
    db = Database()  # default data/mirror.sqlite the running server reads

    if reset:
        removed = db.delete_lims(LIMS)
        print(f"reset: removed {removed} existing rows for {LIMS}")

    # Mode 1 (designated child L-7): baseline vs strategy, engine-driven.
    base_frames, _ = stream_away()
    sid = db.start_session("mode1", "baseline", "6B",
                           [{"lims": LIMS, "zone": ZONE, "consent": True}])
    persist_results(db, sid, "mode1", run_offline(base_frames, Mode1Engine({LIMS: ZONE})))
    print(f"seeded mode1 baseline session {sid}")

    strat_frames, _ = stream_three_raises()
    sid = db.start_session("mode1", "strategy", "6B",
                           [{"lims": LIMS, "zone": ZONE, "consent": True}])
    persist_results(db, sid, "mode1", run_offline(strat_frames, Mode1Engine({LIMS: ZONE})))
    print(f"seeded mode1 strategy session {sid}")

    # Mode 2 (whole class): two anonymous aggregate sessions, engine-driven.
    for _ in range(2):
        frames, truth = stream_class()
        sid = db.start_session("mode2", "none", "6B")
        persist_results(db, sid, "mode2", run_offline(frames, Mode2Engine()))
        print(f"seeded mode2 session {sid} (truth {truth})")

    print("sessions now in DB:", [s["id"] for s in db.list_sessions()])
    print("mode1 LIMS codes:", db.list_mode1_lims())
    db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed demo data for Classroom Mirror.")
    parser.add_argument("--reset", action="store_true",
                        help=f"erase existing {LIMS} rows before seeding")
    args = parser.parse_args(argv)
    seed(reset=args.reset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
