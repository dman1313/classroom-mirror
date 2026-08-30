"""Classroom Mirror V2 teacher-desk product (Windows and macOS)."""

__all__ = ["create_app"]


def create_app(camera_index: int | None = None):
    from .server import create_app as _create

    return _create(camera_index)
