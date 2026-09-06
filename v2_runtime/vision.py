"""Privacy-safe motion analytics for the V2 movement dashboard.

This module turns in-memory camera frames into abstract *motion* signals only.
It never recognises faces, never builds a biometric template, and never writes,
encodes, or returns pixel data. It reduces each frame to a small grayscale
motion field and reports the location and energy of movement blobs. Everything
downstream (sticky anonymous numbers, sensitivity, recap) is built on these
abstract signals, not on the picture of a person.

Only NumPy is required, so the analytics run on a headless machine with a
synthetic source and identically on a real USB camera frame.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np


GRID_HEIGHT = 48
GRID_WIDTH = 64


@dataclass(frozen=True)
class MotionBlob:
    """One region of sustained movement, described abstractly (no pixels)."""

    x: float
    y: float
    energy: float
    area: float


def _to_small_gray(frame: np.ndarray) -> np.ndarray:
    """Reduce any frame to a small float grayscale grid in [0, 255]."""
    array = np.asarray(frame)
    if array.ndim == 3:
        gray = array[..., :3].astype(np.float32).mean(axis=2)
    elif array.ndim == 2:
        gray = array.astype(np.float32)
    else:
        raise ValueError("frame must be a 2D or 3D array")
    if gray.shape[0] < 2 or gray.shape[1] < 2:
        raise ValueError("frame is too small to analyse")

    rows = np.linspace(0, gray.shape[0] - 1, GRID_HEIGHT).astype(np.intp)
    cols = np.linspace(0, gray.shape[1] - 1, GRID_WIDTH).astype(np.intp)
    return gray[np.ix_(rows, cols)]


def _dilate(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    """Grow the motion mask by one cell per iteration (4-neighbourhood).

    Bridges the small gaps a single moving shape leaves between its leading and
    trailing edges so it stays one blob instead of splitting into two numbers.
    """
    grown = mask
    for _ in range(iterations):
        padded = np.pad(grown, 1)
        grown = (
            grown
            | padded[2:, 1:-1]
            | padded[:-2, 1:-1]
            | padded[1:-1, 2:]
            | padded[1:-1, :-2]
        )
    return grown


def _label_components(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    """4-connected components over the small motion mask (pure Python BFS)."""
    height, width = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    components: list[list[tuple[int, int]]] = []
    for start_r in range(height):
        for start_c in range(width):
            if not mask[start_r, start_c] or seen[start_r, start_c]:
                continue
            queue = deque([(start_r, start_c)])
            seen[start_r, start_c] = True
            cells: list[tuple[int, int]] = []
            while queue:
                r, c = queue.popleft()
                cells.append((r, c))
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nr, nc = r + dr, c + dc
                    if (
                        0 <= nr < height
                        and 0 <= nc < width
                        and mask[nr, nc]
                        and not seen[nr, nc]
                    ):
                        seen[nr, nc] = True
                        queue.append((nr, nc))
            components.append(cells)
    return components


class MotionDetector:
    """Frame-difference motion field. Holds only the previous small grayscale.

    The detector keeps no picture: the single retained array is a 64x48 blurred
    brightness grid, from which no face or identity can be reconstructed.
    """

    def __init__(
        self,
        *,
        pixel_threshold: float = 18.0,
        min_area_cells: int = 8,
        dilation: int = 2,
    ) -> None:
        if pixel_threshold <= 0:
            raise ValueError("pixel_threshold must be positive")
        if min_area_cells < 1:
            raise ValueError("min_area_cells must be at least 1")
        if dilation < 0:
            raise ValueError("dilation must be non-negative")
        self.pixel_threshold = float(pixel_threshold)
        self.min_area_cells = int(min_area_cells)
        self.dilation = int(dilation)
        self._previous: np.ndarray | None = None
        self._total_cells = GRID_HEIGHT * GRID_WIDTH

    def reset(self) -> None:
        self._previous = None

    def update(self, frame: np.ndarray) -> list[MotionBlob]:
        """Return the movement blobs between this frame and the previous one."""
        small = _to_small_gray(frame)
        previous = self._previous
        self._previous = small
        if previous is None:
            return []

        diff = np.abs(small - previous)
        mask = diff > self.pixel_threshold
        if not mask.any():
            return []
        if self.dilation:
            mask = _dilate(mask, self.dilation)

        blobs: list[MotionBlob] = []
        for cells in _label_components(mask):
            if len(cells) < self.min_area_cells:
                continue
            rows = np.fromiter((c[0] for c in cells), dtype=np.float32)
            cols = np.fromiter((c[1] for c in cells), dtype=np.float32)
            energy = float(np.mean([diff[r, c] for r, c in cells]) / 255.0)
            blobs.append(
                MotionBlob(
                    x=float(cols.mean() / (GRID_WIDTH - 1)),
                    y=float(rows.mean() / (GRID_HEIGHT - 1)),
                    energy=min(1.0, energy),
                    area=len(cells) / self._total_cells,
                )
            )
        blobs.sort(key=lambda blob: blob.area, reverse=True)
        return blobs
