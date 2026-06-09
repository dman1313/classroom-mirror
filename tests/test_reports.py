"""Report criteria 12-14: the numbers a teacher actually reads."""
import pytest

from app import reports
from app.camera import persist_results
from app.session import Mode2Engine, run_offline
from tests.criteria import evidence
from tests.fixtures import build_mode1_db, build_mode2_db, stream_class


@pytest.mark.criterion(12)
def test_mode1_before_after_report(tmp_db):
    build_mode1_db(tmp_db)
    html = reports.mode1_report_html(tmp_db, "L-7")
    for fragment in (
        "Hand raises per 10 minutes: baseline 5.0",
        "strategy 15.0",
        "(+10.0)",
        "Time at their spot: baseline 50%",
        "strategy 80%",
        "(+30 points)",
        "Most common movement level: baseline low",
        "strategy medium",
        "not a judgment of any child",
    ):
        assert fragment in html, f"missing from report: {fragment!r}"
    evidence(12, "report for fixture child L-7 states: raises/10min 5.0 -> 15.0 "
                 "(+10.0), at spot 50% -> 80% (+30 points), movement low -> medium")


@pytest.mark.criterion(13)
def test_mode2_summary_end_to_end(tmp_db):
    frames, truth = stream_class()
    sid = tmp_db.start_session("mode2", "none", "6B")
    persist_results(tmp_db, sid, "mode2", run_offline(frames, Mode2Engine()))
    html = reports.mode2_summary_html(tmp_db, sid)
    assert f"Hand raises (class total): {truth['raises']}" in html
    assert f"People in view (typical): {truth['bodies']}" in html
    assert "Minutes observed: 2" in html
    assert "<svg" in html  # the movement timeline strip
    evidence(13, "class fixture flowed engine -> database -> report: summary "
                 f"shows {truth['raises']} raises, {truth['bodies']} people, "
                 "movement timeline rendered")


@pytest.mark.criterion(14)
def test_mode2_compare_side_by_side(tmp_db):
    sid_a, sid_b = build_mode2_db(tmp_db)
    html = reports.mode2_compare_html(tmp_db, sid_a, sid_b)
    assert f"Session {sid_a}" in html and f"Session {sid_b}" in html
    assert html.count("Hand raises (class total): 2") == 2
    assert "cols" in html  # side-by-side layout
    evidence(14, f"sessions {sid_a} and {sid_b} rendered side by side, "
                 "each with its own totals and movement strip")
