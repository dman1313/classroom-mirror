import socket
import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.criteria import OUTCOMES  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "criterion(num): maps this test to a contract criterion")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    out = yield
    rep = out.get_result()
    if rep.when != "call":
        return
    marker = item.get_closest_marker("criterion")
    if marker is None:
        return
    num = marker.args[0]
    failure = ""
    if rep.failed and rep.longrepr is not None:
        failure = str(rep.longrepr).strip().splitlines()[-1][:200]
    OUTCOMES.setdefault(num, []).append((rep.passed, item.name, failure))


@pytest.fixture
def tmp_db(tmp_path):
    from app.db import Database
    db = Database(data_dir=str(tmp_path / "data"))
    yield db
    db.close()


class _LoopbackOnly:
    """Blocks every network connection that is not loopback. Used by the
    guardrail-5 test: the app must run a full session without one attempt."""

    LOOPBACK = ("127.0.0.1", "localhost", "::1")

    def __init__(self):
        self.attempts = []

    def __enter__(self):
        self._connect = socket.socket.connect
        self._connect_ex = socket.socket.connect_ex
        guard = self

        def is_allowed(address):
            if isinstance(address, str):       # unix socket
                return True
            host = address[0]
            return host in guard.LOOPBACK or host.startswith("127.")

        def connect(sock, address):
            if not is_allowed(address):
                guard.attempts.append(address)
                raise AssertionError(f"Outbound network attempt to {address}")
            return guard._connect(sock, address)

        def connect_ex(sock, address):
            if not is_allowed(address):
                guard.attempts.append(address)
                raise AssertionError(f"Outbound network attempt to {address}")
            return guard._connect_ex(sock, address)

        socket.socket.connect = connect
        socket.socket.connect_ex = connect_ex
        return self

    def __exit__(self, *exc):
        socket.socket.connect = self._connect
        socket.socket.connect_ex = self._connect_ex
        return False


@pytest.fixture
def loopback_only():
    with _LoopbackOnly() as guard:
        yield guard
