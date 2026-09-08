"""Fail-closed pytest policy for V2 runtime acceptance."""

pytest_plugins = ("v2_tests.strict_acceptance",)


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "camera: requires an explicitly selected real USB camera"
    )
