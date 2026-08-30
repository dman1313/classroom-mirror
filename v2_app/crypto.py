"""User-local integrity wrap for anonymous templates. Not a substitute for OS DPAPI."""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path

_MAGIC = b"CM2T"


def load_or_create_key(path: Path) -> bytes:
    if path.is_file():
        key = path.read_bytes()
        if len(key) == 32:
            return key
    path.parent.mkdir(parents=True, exist_ok=True)
    key = os.urandom(32)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, key)
    finally:
        os.close(fd)
    return key


def wrap(plaintext: bytes, key: bytes) -> bytes:
    digest = hmac.new(key, plaintext, hashlib.sha256).digest()
    return _MAGIC + digest + plaintext


def unwrap(blob: bytes, key: bytes) -> bytes:
    if len(blob) < 4 + 32 or not blob.startswith(_MAGIC):
        raise ValueError("template blob is not a Classroom Mirror V2 record")
    digest = blob[4:36]
    plaintext = blob[36:]
    expected = hmac.new(key, plaintext, hashlib.sha256).digest()
    if not hmac.compare_digest(digest, expected):
        raise ValueError("template blob failed integrity check")
    return plaintext
