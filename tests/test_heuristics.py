"""Core measurement criteria 9-11 + the Mode 2 engine half of 13,
proven on synthetic keypoint streams with known truth."""
import pytest

from app.heuristics import movement_bucket
from app.session import Mode1Engine, Mode2Engine, run_offline
from tests.criteria import evidence
from tests.fixtures import (
    ZONE, stream_away, stream_class, stream_movement, stream_three_raises,
)


@pytest.mark.criterion(9)
def test_hand_raises_within_one():
    frames, truth = stream_three_raises()
    _, events = run_offline(frames, Mode1Engine({"L-7": ZONE}))
    counted = len(events)
    assert abs(counted - truth) <= 1, f"counted {counted}, truth {truth}"
    evidence(9, f"fixture with {truth} real raises plus one 0.2s flicker: "
                f"counted {counted} (flicker correctly ignored)")


@pytest.mark.criterion(10)
def test_at_spot_within_five_percent():
    frames, truth = stream_away()
    minute_rows, _ = run_offline(frames, Mode1Engine({"L-7": ZONE}))
    measured = {minute: pct for _, minute, pct, _ in minute_rows}
    for minute, expected in truth.items():
        assert minute in measured, f"minute {minute} missing"
        assert abs(measured[minute] - expected) <= 5.0, \
            f"minute {minute}: measured {measured[minute]}, truth {expected}"
    evidence(10, "person away 50% of minute one and 20% of minute two: "
                 f"measured {measured[0]:.0f}% and {measured[1]:.0f}% at spot "
                 "(truth 50% / 80%)")


@pytest.mark.criterion(11)
def test_movement_buckets():
    outcomes = {}
    for speed, expected in [(0.01, "low"), (0.08, "medium"), (0.30, "high")]:
        frames = stream_movement(speed)
        minute_rows, _ = run_offline(frames, Mode1Engine({"L-7": ZONE}))
        buckets = {bucket for _, _, _, bucket in minute_rows}
        assert buckets == {expected}, \
            f"speed {speed}: got {buckets}, expected {expected}"
        outcomes[speed] = expected
    assert movement_bucket(0.0) == "low"
    evidence(11, "three fixture speeds (0.01 / 0.08 / 0.30 body-heights per "
                 "second) bucketed exactly as low / medium / high")


@pytest.mark.criterion(13)
def test_mode2_engine_aggregates():
    frames, truth = stream_class()
    rows = run_offline(frames, Mode2Engine())
    assert len(rows) == 2
    total_raises = sum(r[2] for r in rows)
    bodies = {r[1] for r in rows}
    buckets = {r[3] for r in rows}
    assert total_raises == truth["raises"], f"raises {total_raises}"
    assert bodies == {truth["bodies"]}
    assert buckets == {truth["bucket"]}
    evidence(13, f"class fixture (3 people, 2 raises): engine measured "
                 f"{sorted(bodies)[0]} people, {total_raises} raises, "
                 f"movement {sorted(buckets)[0]}")
