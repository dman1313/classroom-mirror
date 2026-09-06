"""The V2 movement engine: sticky numbers + yellow/red cues + a neutral recap.

The engine is the teacher-visible product logic. It consumes in-memory frames,
produces an abstract live picture (anonymous numbers with a calm / yellow / red
movement cue), and, on Stop, an uncertainty-first recap. It stores no pixels,
no identities, and no per-number ranking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time

import numpy as np

from .sensitivity import SensitivityProfile
from .tracking import Marker, MarkerTracker
from .vision import MotionDetector


LEVEL_CALM = 0
LEVEL_YELLOW = 1
LEVEL_RED = 2
LEVEL_NAMES = {LEVEL_CALM: "calm", LEVEL_YELLOW: "yellow", LEVEL_RED: "red"}

_ENERGY_SMOOTHING = 0.65


@dataclass
class MarkerView:
    """Abstract, sendable description of one anonymous number (no pixels)."""

    number: int
    x: float
    y: float
    level: str


@dataclass
class Recap:
    """Neutral, aggregate-only end-of-session summary."""

    started_at: float
    ended_at: float
    frames: int
    sensitivity_name: str
    sensitivity_version: str
    numbers_seen: int
    peak_concurrent: int
    yellow_episodes: int
    red_episodes: int
    yellow_seconds: float
    red_seconds: float

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.ended_at - self.started_at)

    def to_lines(self) -> list[str]:
        minutes = self.duration_seconds / 60.0
        lines = [
            f"Session length: about {minutes:.1f} minute(s).",
            f"Sensitivity: {self.sensitivity_name} "
            f"(profile {self.sensitivity_version}).",
            f"Anonymous movement numbers seen: {self.numbers_seen} "
            f"(at most {self.peak_concurrent} at once).",
            f"Times a number showed sustained movement (yellow): "
            f"{self.yellow_episodes}.",
            f"Times movement stayed high enough to reach red: "
            f"{self.red_episodes}.",
            "These are movement signals only. They may be caused by many "
            "ordinary things and are not a measure of behaviour, attention, "
            "character, or anything about a specific person.",
            "Numbers are positions on screen, not identities, and were not "
            "saved. Nothing from this session is kept unless you keep this "
            "note yourself.",
        ]
        return lines


class MovementEngine:
    """Per-frame movement analysis with sticky numbers and level cues."""

    def __init__(
        self,
        profile: SensitivityProfile,
        *,
        detector: MotionDetector | None = None,
        tracker: MarkerTracker | None = None,
    ) -> None:
        self.profile = profile
        self.detector = detector or MotionDetector()
        self.tracker = tracker or MarkerTracker()
        self._frames = 0
        self._started_at: float | None = None
        self._last_at: float | None = None
        self._peak_concurrent = 0
        self._yellow_episodes = 0
        self._red_episodes = 0
        self._yellow_frame_count = 0
        self._red_frame_count = 0
        self._level_frame_span = 0.1

    def update(self, frame: np.ndarray, now: float | None = None) -> list[MarkerView]:
        timestamp = time.monotonic() if now is None else now
        if self._started_at is None:
            self._started_at = timestamp
        if self._last_at is not None:
            self._level_frame_span = max(0.0, timestamp - self._last_at)
        self._last_at = timestamp
        self._frames += 1

        blobs = self.detector.update(frame)
        markers = self.tracker.update(blobs)
        self._peak_concurrent = max(self._peak_concurrent, len(markers))

        views: list[MarkerView] = []
        for marker in markers:
            level = self._advance_level(marker)
            views.append(
                MarkerView(
                    number=marker.number,
                    x=round(marker.x, 4),
                    y=round(marker.y, 4),
                    level=LEVEL_NAMES[level],
                )
            )
            if level == LEVEL_YELLOW:
                self._yellow_frame_count += 1
            elif level == LEVEL_RED:
                self._red_frame_count += 1
        views.sort(key=lambda view: view.number)
        return views

    def _advance_level(self, marker: Marker) -> int:
        state = marker.extra
        smoothed = state.get("energy", 0.0)
        smoothed = _ENERGY_SMOOTHING * smoothed + (1 - _ENERGY_SMOOTHING) * marker.step
        state["energy"] = smoothed

        profile = self.profile
        up_yellow = state.get("up_yellow", 0) + 1 if smoothed >= profile.yellow_energy else 0
        up_red = state.get("up_red", 0) + 1 if smoothed >= profile.red_energy else 0
        calm = state.get("calm", 0) + 1 if smoothed <= profile.calm_energy else 0
        state["up_yellow"] = up_yellow
        state["up_red"] = up_red
        state["calm"] = calm

        level = state.get("level", LEVEL_CALM)
        if level == LEVEL_CALM:
            if up_yellow >= profile.yellow_sustain_frames:
                level = LEVEL_YELLOW
                self._yellow_episodes += 1
                state["calm"] = 0
        elif level == LEVEL_YELLOW:
            if up_red >= profile.red_sustain_frames:
                level = LEVEL_RED
                self._red_episodes += 1
                state["calm"] = 0
            elif calm >= profile.resolve_frames:
                level = LEVEL_CALM
        elif level == LEVEL_RED:
            if calm >= profile.resolve_frames:
                level = LEVEL_YELLOW
                state["calm"] = 0

        state["level"] = level
        return level

    def overall_motion(self, views: list[MarkerView]) -> str:
        if any(view.level == "red" for view in views):
            return "red"
        if any(view.level == "yellow" for view in views):
            return "yellow"
        return "calm"

    def recap(self, ended_at: float | None = None) -> Recap:
        end = ended_at if ended_at is not None else (self._last_at or time.monotonic())
        start = self._started_at if self._started_at is not None else end
        span = self._level_frame_span or 0.1
        return Recap(
            started_at=start,
            ended_at=end,
            frames=self._frames,
            sensitivity_name=self.profile.name,
            sensitivity_version=self.profile.version,
            numbers_seen=self.tracker.total_numbers_assigned,
            peak_concurrent=self._peak_concurrent,
            yellow_episodes=self._yellow_episodes,
            red_episodes=self._red_episodes,
            yellow_seconds=round(self._yellow_frame_count * span, 1),
            red_seconds=round(self._red_frame_count * span, 1),
        )
