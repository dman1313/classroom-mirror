"""Pytest plugin that makes non-proof outcomes fail the V2 acceptance run."""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--camera-index",
        action="store",
        type=int,
        help="Enumerated physical USB camera index for the adult-beta smoke.",
    )


@pytest.fixture
def camera_index(request):
    value = request.config.getoption("--camera-index")
    if value is None or value < 0:
        pytest.fail("an enumerated non-negative --camera-index is required")
    return value


def pytest_sessionfinish(session, exitstatus):
    terminal = session.config.pluginmanager.get_plugin("terminalreporter")
    if terminal is None:
        return
    non_proof = sum(
        len(terminal.stats.get(key, ()))
        for key in ("skipped", "xfailed", "xpassed")
    )
    if non_proof and session.exitstatus == pytest.ExitCode.OK:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
