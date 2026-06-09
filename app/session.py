"""Session engines: consume keypoint frames, produce per-minute rows.

Mode1Engine — designated zones only. Bodies outside the zones are ignored
entirely: never measured, never stored.

Mode2Engine — the whole room as aggregates. There is no per-body output at
all; the engine only ever emits room-level numbers (guardrail 7).
"""
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from .heuristics import (
    CentroidTracker, HandRaiseDetector, KeypointFrame, Person,
    centroid_speed, movement_bucket, person_in_zone,
)

Zone = Tuple[float, float, float, float]


class _MinuteAcc:
    def __init__(self):
        self.frames = 0
        self.present = 0
        self.speeds: List[float] = []

    def bucket(self) -> str:
        mean = sum(self.speeds) / len(self.speeds) if self.speeds else 0.0
        return movement_bucket(mean)


class Mode1Engine:
    def __init__(self, zones: Dict[str, Zone]):
        self.zones = zones
        self.raise_detectors = {lims: HandRaiseDetector() for lims in zones}
        self.minutes: Dict[str, Dict[int, _MinuteAcc]] = {
            lims: defaultdict(_MinuteAcc) for lims in zones
        }
        self.events: List[Tuple[str, float]] = []  # (lims, t)
        self._prev: Dict[str, Optional[Tuple[Person, float]]] = {l: None for l in zones}

    def update(self, frame: KeypointFrame):
        minute = int(frame.t // 60)
        for lims, zone in self.zones.items():
            acc = self.minutes[lims][minute]
            acc.frames += 1
            person = person_in_zone(frame.persons, zone)
            if person is not None:
                acc.present += 1
                prev = self._prev[lims]
                if prev is not None:
                    speed = centroid_speed(prev[0], prev[1], person, frame.t)
                    if speed is not None:
                        acc.speeds.append(speed)
                self._prev[lims] = (person, frame.t)
            else:
                self._prev[lims] = None
            if self.raise_detectors[lims].update(frame.t, person):
                self.events.append((lims, frame.t))

    def finish(self):
        """Returns (minute_rows, event_rows) ready for the database."""
        minute_rows = []
        for lims, by_minute in self.minutes.items():
            for minute in sorted(by_minute):
                acc = by_minute[minute]
                if acc.frames == 0:
                    continue
                pct = 100.0 * acc.present / acc.frames
                minute_rows.append((lims, minute, round(pct, 1), acc.bucket()))
        event_rows = [(lims, round(t, 2)) for lims, t in self.events]
        return minute_rows, event_rows


class Mode2Engine:
    def __init__(self):
        self.tracker = CentroidTracker()
        self.raises_by_minute: Dict[int, int] = defaultdict(int)
        self.speeds_by_minute: Dict[int, List[float]] = defaultdict(list)
        self.bodies_samples: Dict[int, List[int]] = defaultdict(list)

    def update(self, frame: KeypointFrame):
        minute = int(frame.t // 60)
        matches = self.tracker.update(frame)
        self.bodies_samples[minute].append(len(frame.persons))
        for track, person, speed in matches:
            if speed is not None:
                self.speeds_by_minute[minute].append(speed)
            if track.raise_detector.update(frame.t, person):
                self.raises_by_minute[minute] += 1

    def finish(self):
        """Returns minute rows: (minute, bodies_detected, hand_raises, bucket)."""
        rows = []
        for minute in sorted(self.bodies_samples):
            samples = sorted(self.bodies_samples[minute])
            bodies = samples[len(samples) // 2] if samples else 0  # median
            speeds = self.speeds_by_minute[minute]
            mean = sum(speeds) / len(speeds) if speeds else 0.0
            rows.append((minute, bodies, self.raises_by_minute[minute],
                         movement_bucket(mean)))
        return rows


def run_offline(frames, engine):
    """Drive an engine from any iterable of KeypointFrames (tests, demos)."""
    for frame in frames:
        engine.update(frame)
    return engine.finish()
