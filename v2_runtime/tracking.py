"""Anonymous, position-based sticky numbers for the V2 movement dashboard.

These numbers are *not* biometric. A number is assigned to a moving region by
its position on the screen and follows that region from frame to frame using
nearest-neighbour matching. Nothing about a face, body, or identity is stored:
if a person leaves and someone else stands in the same spot, the tool cannot and
does not try to tell them apart. Numbers reset every session and never persist.

This deliberately avoids the biometric face-template path called out as the
privacy cliff in AUDIT.md and V2-DELTA.md; that work is out of scope here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .vision import MotionBlob


@dataclass
class Marker:
    """One anonymous, position-tracked movement number for this session."""

    number: int
    x: float
    y: float
    energy: float
    step: float = 0.0
    missed: int = 0
    seen_frames: int = 1
    extra: dict = field(default_factory=dict)


def _distance(ax: float, ay: float, bx: float, by: float) -> float:
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


class MarkerTracker:
    """Greedy nearest-neighbour tracker producing sticky anonymous numbers.

    A marker survives brief disappearance (occlusion, a missed frame) for
    ``max_missed`` updates before its number is retired. Numbers are handed out
    sequentially and are never reused within a session.
    """

    def __init__(
        self,
        *,
        max_match_distance: float = 0.18,
        max_missed: int = 12,
        position_smoothing: float = 0.5,
    ) -> None:
        if not 0 < max_match_distance <= 2:
            raise ValueError("max_match_distance must be in (0, 2]")
        if max_missed < 0:
            raise ValueError("max_missed must be non-negative")
        if not 0 <= position_smoothing < 1:
            raise ValueError("position_smoothing must be in [0, 1)")
        self.max_match_distance = float(max_match_distance)
        self.max_missed = int(max_missed)
        self.position_smoothing = float(position_smoothing)
        self._markers: dict[int, Marker] = {}
        self._next_number = 1

    @property
    def markers(self) -> list[Marker]:
        """Currently visible markers (those matched on the last update)."""
        return [m for m in self._markers.values() if m.missed == 0]

    @property
    def total_numbers_assigned(self) -> int:
        return self._next_number - 1

    def update(self, blobs: list[MotionBlob]) -> list[Marker]:
        """Match blobs to existing numbers; create/retire numbers as needed."""
        unmatched_blobs = list(range(len(blobs)))
        matched_markers: set[int] = set()

        pairs: list[tuple[float, int, int]] = []
        for number, marker in self._markers.items():
            for blob_index in unmatched_blobs:
                blob = blobs[blob_index]
                dist = _distance(marker.x, marker.y, blob.x, blob.y)
                if dist <= self.max_match_distance:
                    pairs.append((dist, number, blob_index))
        pairs.sort(key=lambda item: item[0])

        used_blobs: set[int] = set()
        for _dist, number, blob_index in pairs:
            if number in matched_markers or blob_index in used_blobs:
                continue
            blob = blobs[blob_index]
            marker = self._markers[number]
            marker.step = _distance(marker.x, marker.y, blob.x, blob.y)
            smoothing = self.position_smoothing
            marker.x = smoothing * marker.x + (1 - smoothing) * blob.x
            marker.y = smoothing * marker.y + (1 - smoothing) * blob.y
            marker.energy = blob.energy
            marker.missed = 0
            marker.seen_frames += 1
            matched_markers.add(number)
            used_blobs.add(blob_index)

        for blob_index in unmatched_blobs:
            if blob_index in used_blobs:
                continue
            blob = blobs[blob_index]
            number = self._next_number
            self._next_number += 1
            self._markers[number] = Marker(
                number=number, x=blob.x, y=blob.y, energy=blob.energy
            )
            matched_markers.add(number)

        for number, marker in list(self._markers.items()):
            if number in matched_markers:
                continue
            marker.missed += 1
            marker.energy = 0.0
            marker.step = 0.0
            if marker.missed > self.max_missed:
                del self._markers[number]

        return self.markers
