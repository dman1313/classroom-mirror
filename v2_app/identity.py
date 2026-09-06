"""Anonymous sticky numbers backed by local face templates. No names."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field

import numpy as np

from . import crypto

MATCH_FLOOR = 0.82
TEMPLATE_SIZE = 32
MAX_IDS = 80
TTL_SECONDS = 30 * 24 * 3600
# Mean-centered crops below this energy are lights/walls, not a face.
MIN_CROP_NORM = 1.0


@dataclass
class Identity:
    number: int
    vector: list[float]
    created_at: float
    last_seen: float


def vector_from_gray(gray) -> list[float]:
    arr = np.asarray(gray, dtype=np.float32)
    if arr.size == 0:
        raise ValueError("empty face crop")
    if arr.ndim == 3:
        arr = arr.mean(axis=2)
    # Resize without cv2 so tests stay dependency-light.
    ys = np.linspace(0, arr.shape[0] - 1, TEMPLATE_SIZE)
    xs = np.linspace(0, arr.shape[1] - 1, TEMPLATE_SIZE)
    grid_y, grid_x = np.meshgrid(ys, xs, indexing="ij")
    sampled = arr[
        np.clip(np.rint(grid_y).astype(int), 0, arr.shape[0] - 1),
        np.clip(np.rint(grid_x).astype(int), 0, arr.shape[1] - 1),
    ]
    flat = sampled.reshape(-1)
    flat = flat - float(flat.mean())
    energy = float(np.linalg.norm(flat))
    if energy < MIN_CROP_NORM:
        raise ValueError("low-contrast face crop")
    return (flat / energy).astype(np.float32).tolist()


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) + 1e-9
    nb = math.sqrt(sum(y * y for y in b)) + 1e-9
    return dot / (na * nb)


@dataclass
class IdentityBook:
    identities: dict[int, Identity] = field(default_factory=dict)
    _next: int = 1

    def expire(self, now: float, ttl: float = TTL_SECONDS) -> None:
        dead = [
            n
            for n, ident in self.identities.items()
            if now - ident.last_seen > ttl
        ]
        for n in dead:
            del self.identities[n]

    def match_or_create(self, vector: list[float], now: float) -> tuple[int, float]:
        self.expire(now)
        if math.sqrt(sum(x * x for x in vector)) < 0.5:
            return 0, 0.0
        best_n = None
        best_score = MATCH_FLOOR
        for ident in self.identities.values():
            score = cosine(vector, ident.vector)
            if score > best_score:
                best_score = score
                best_n = ident.number
        if best_n is not None:
            ident = self.identities[best_n]
            ident.last_seen = now
            ident.vector = _blend(ident.vector, vector)
            return best_n, best_score
        if len(self.identities) >= MAX_IDS:
            return 0, 0.0
        number = self._next
        while number in self.identities:
            number += 1
        self._next = number + 1
        self.identities[number] = Identity(number, vector, now, now)
        return number, 1.0

    def delete_one(self, number: int) -> bool:
        return self.identities.pop(int(number), None) is not None

    def delete_all(self) -> int:
        n = len(self.identities)
        self.identities.clear()
        self._next = 1
        return n

    def dump(self) -> bytes:
        payload = {
            "next": self._next,
            "identities": [
                {
                    "number": ident.number,
                    "vector": ident.vector,
                    "created_at": ident.created_at,
                    "last_seen": ident.last_seen,
                }
                for ident in self.identities.values()
            ],
        }
        return json.dumps(payload).encode("utf-8")

    @classmethod
    def load(cls, raw: bytes) -> IdentityBook:
        data = json.loads(raw.decode("utf-8"))
        book = cls()
        book._next = int(data.get("next") or 1)
        for row in data.get("identities") or []:
            ident = Identity(
                number=int(row["number"]),
                vector=[float(x) for x in row["vector"]],
                created_at=float(row["created_at"]),
                last_seen=float(row["last_seen"]),
            )
            book.identities[ident.number] = ident
        return book

    def save_wrapped(self, path, key: bytes | None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(crypto.seal(self.dump(), key))

    @classmethod
    def load_wrapped(cls, path, key: bytes | None) -> IdentityBook:
        if not path.is_file():
            return cls()
        return cls.load(crypto.unseal(path.read_bytes(), key))


def _blend(old: list[float], new: list[float], rate: float = 0.15) -> list[float]:
    return [((1 - rate) * a) + (rate * b) for a, b in zip(old, new)]


def now() -> float:
    return time.time()
