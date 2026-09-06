"""Fail-closed network and filesystem policy for the Windows V2 runtime."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import socket
from typing import Callable, Sequence


LOOPBACK_HOST = "127.0.0.1"
APP_DIRECTORY = "ClassroomMirror"

_ALLOWLISTED_FILES = frozenset(
    {
        PurePosixPath("state/classroom-mirror.sqlite3"),
        PurePosixPath("state/classroom-mirror.sqlite3-journal"),
        PurePosixPath("state/classroom-mirror.sqlite3-shm"),
        PurePosixPath("state/classroom-mirror.sqlite3-wal"),
        PurePosixPath("state/identities.bin"),
        PurePosixPath("logs/runtime.log"),
        PurePosixPath("config/runtime.json"),
        PurePosixPath("config/template.key"),
    }
)
_TEXT_FILES = frozenset(
    {
        PurePosixPath("logs/runtime.log"),
        PurePosixPath("config/runtime.json"),
    }
)


class PolicyViolation(ValueError):
    """Raised before an unsafe runtime operation reaches the OS."""


def validate_bind_host(host: str) -> str:
    """Accept only the literal IPv4 loopback address used by the service."""
    if host != LOOPBACK_HOST:
        raise PolicyViolation(
            f"service host must be exactly {LOOPBACK_HOST}; refused {host!r}"
        )
    return host


class RuntimeNetworkPolicy:
    """The only runtime connector; it never resolves or calls outbound hosts."""

    def __init__(self, connector: Callable = socket.create_connection):
        self._connector = connector
        self._outbound_attempts: list[tuple] = []

    @property
    def outbound_attempts(self) -> tuple[tuple, ...]:
        return tuple(self._outbound_attempts)

    def connect(self, address: Sequence, timeout=None):
        try:
            normalized = tuple(address)
            host = normalized[0]
        except (IndexError, TypeError):
            raise PolicyViolation("runtime connection address is invalid") from None

        if host != LOOPBACK_HOST:
            self._outbound_attempts.append(normalized)
            raise PolicyViolation(
                f"outbound runtime connection refused before socket attempt: {host!r}"
            )
        return self._connector(normalized, timeout=timeout)


class RuntimeFilePolicy:
    """Resolve V2 writes beneath Local AppData against an exact allowlist."""

    def __init__(self, local_app_data: os.PathLike | str | None = None):
        base = local_app_data or os.environ.get("LOCALAPPDATA")
        if not base:
            raise PolicyViolation("LOCALAPPDATA is required for V2 runtime writes")
        self.local_app_data = Path(base).resolve()
        self.root = (self.local_app_data / APP_DIRECTORY).resolve()

    def resolve_write(self, relative_path: os.PathLike | str) -> Path:
        raw = os.fspath(relative_path)
        if not isinstance(raw, str) or not raw or "\x00" in raw:
            raise PolicyViolation("runtime write path is invalid")

        windows_path = PureWindowsPath(raw)
        portable_path = PurePosixPath(raw.replace("\\", "/"))
        if windows_path.is_absolute() or windows_path.drive:
            raise PolicyViolation("absolute runtime write paths are forbidden")
        if any(part in ("", ".", "..") for part in portable_path.parts):
            raise PolicyViolation("runtime write path traversal is forbidden")
        if portable_path not in _ALLOWLISTED_FILES:
            raise PolicyViolation(f"runtime write is not allowlisted: {raw!r}")

        target = (self.root / Path(*portable_path.parts)).resolve()
        try:
            target.relative_to(self.root)
        except ValueError:
            raise PolicyViolation("runtime write escaped the per-user data root") from None
        return target

    def open_text(self, relative_path: os.PathLike | str, mode: str = "a"):
        """Open an allowlisted text/config/log file, creating only its parent."""
        if mode not in {"a", "w", "x"}:
            raise PolicyViolation("runtime text writes require mode a, w, or x")
        portable_path = PurePosixPath(os.fspath(relative_path).replace("\\", "/"))
        if portable_path not in _TEXT_FILES:
            raise PolicyViolation("runtime text API accepts only the config and log files")
        target = self.resolve_write(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        return target.open(mode, encoding="utf-8")
