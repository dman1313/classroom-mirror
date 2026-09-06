"""Seal anonymous templates. Windows uses DPAPI; elsewhere a local HMAC wrap."""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path

_MAGIC = b"CM2T"
_DPAPI_MAGIC = b"CM2D"


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


def uses_dpapi() -> bool:
    return os.name == "nt"


def seal(plaintext: bytes, key: bytes | None) -> bytes:
    if key is None:
        return _dpapi_protect(plaintext)
    return wrap(plaintext, key)


def unseal(blob: bytes, key: bytes | None) -> bytes:
    if blob.startswith(_DPAPI_MAGIC):
        return _dpapi_unprotect(blob[len(_DPAPI_MAGIC) :])
    if key is None:
        raise ValueError("HMAC template blob requires a local wrap key")
    return unwrap(blob, key)


def _dpapi_protect(plaintext: bytes) -> bytes:
    encrypted = _crypt_protect_data(plaintext)
    return _DPAPI_MAGIC + encrypted


def _dpapi_unprotect(blob: bytes) -> bytes:
    return _crypt_unprotect_data(blob)


def _crypt_protect_data(plaintext: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    buffer = ctypes.create_string_buffer(plaintext)
    blob_in = DATA_BLOB(len(plaintext), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    blob_out = DATA_BLOB()
    if not crypt32.CryptProtectData(
        ctypes.byref(blob_in),
        "ClassroomMirrorV2",
        None,
        None,
        None,
        0,
        ctypes.byref(blob_out),
    ):
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def _crypt_unprotect_data(blob: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    buffer = ctypes.create_string_buffer(blob)
    blob_in = DATA_BLOB(len(blob), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    blob_out = DATA_BLOB()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(blob_in),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(blob_out),
    ):
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)
