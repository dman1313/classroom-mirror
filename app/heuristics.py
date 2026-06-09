"""Pure behaviour heuristics over keypoint streams.

Everything here is a plain function of geometry over time — no camera, no
model, no I/O — so criteria 9-11 and 13 are provable on synthetic streams
with known truth.

Coordinates are normalized to the image (0..1, y grows downward).
"""
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

Point = Tuple[float, float, float]  # x, y, confidence

# Movement buckets, in body-heights moved per second (centroid speed).
MOVE_LOW = 0.04
MOVE_MED = 0.15

MIN_KP_CONF = 0.3


@dataclass
class Person:
    kps: Dict[str, Point]
    bbox: Tuple[float, float, float, float]  # x, y, w, h (top-left, normalized)

    @property
    def centroid(self) -> Tuple[float, float]:
        x, y, w, h = self.bbox
        return (x + w / 2, y + h / 2)

    @property
    def height(self) -> float:
        return max(self.bbox[3], 1e-6)


@dataclass
class KeypointFrame:
    t: float  # seconds since session start
    persons: List[Person]


def _kp(person: Person, name: str) -> Optional[Point]:
    p = person.kps.get(name)
    if p is None or p[2] < MIN_KP_CONF:
        return None
    return p


def eye_line_y(person: Person) -> Optional[float]:
    ys = [p[1] for n in ("left_eye", "right_eye", "nose") if (p := _kp(person, n))]
    return sum(ys) / len(ys) if ys else None


def wrist_top_y(person: Person) -> Optional[float]:
    ys = [p[1] for n in ("left_wrist", "right_wrist") if (p := _kp(person, n))]
    return min(ys) if ys else None


def hand_is_up(person: Person, margin: float = 0.05) -> bool:
    eye_y = eye_line_y(person)
    wrist_y = wrist_top_y(person)
    if eye_y is None or wrist_y is None:
        return False
    return wrist_y < eye_y - margin * person.height


class HandRaiseDetector:
    """Fires one event per sustained raise: hand above eye line for at least
    `min_hold` seconds, then a `refractory` pause before the next can count."""

    def __init__(self, min_hold: float = 0.5, refractory: float = 2.0):
        self.min_hold = min_hold
        self.refractory = refractory
        self._raised_since: Optional[float] = None
        self._fired_current = False
        self._last_event_t = -math.inf

    def update(self, t: float, person: Optional[Person]) -> bool:
        if person is None or not hand_is_up(person):
            self._raised_since = None
            self._fired_current = False
            return False
        if self._raised_since is None:
            self._raised_since = t
        held = t - self._raised_since
        if (not self._fired_current and held >= self.min_hold
                and t - self._last_event_t >= self.refractory):
            self._fired_current = True
            self._last_event_t = t
            return True
        return False


def in_zone(person: Person, zone: Tuple[float, float, float, float]) -> bool:
    cx, cy = person.centroid
    zx, zy, zw, zh = zone
    return zx <= cx <= zx + zw and zy <= cy <= zy + zh


def person_in_zone(persons: List[Person],
                   zone: Tuple[float, float, float, float]) -> Optional[Person]:
    """The body whose centroid sits in the zone; nearest to zone center wins."""
    zcx, zcy = zone[0] + zone[2] / 2, zone[1] + zone[3] / 2
    candidates = [p for p in persons if in_zone(p, zone)]
    if not candidates:
        return None
    return min(candidates, key=lambda p: _dist(p.centroid, (zcx, zcy)))


def _dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def centroid_speed(prev: Person, prev_t: float, cur: Person, cur_t: float) -> Optional[float]:
    """Body-heights moved per second between two sightings of the same body."""
    dt = cur_t - prev_t
    if dt <= 0:
        return None
    return _dist(prev.centroid, cur.centroid) / dt / cur.height


def movement_bucket(mean_speed: float) -> str:
    if mean_speed < MOVE_LOW:
        return "low"
    if mean_speed < MOVE_MED:
        return "medium"
    return "high"


# -- simple multi-person tracking for whole-class mode -----------------------

@dataclass
class Track:
    track_id: int
    person: Person
    t: float
    raise_detector: HandRaiseDetector = field(default_factory=HandRaiseDetector)


class CentroidTracker:
    """Greedy nearest-centroid matching. Good enough to keep per-body raise
    state and measure movement; it never identifies anyone — track ids reset
    every session and are never stored."""

    def __init__(self, max_dist: float = 0.08, ttl: float = 1.0):
        self.max_dist = max_dist
        self.ttl = ttl
        self.tracks: List[Track] = []
        self._next_id = 1

    def update(self, frame: KeypointFrame) -> List[Tuple[Track, Person, Optional[float]]]:
        """Returns (track, person, speed) per matched body this frame."""
        pairs = []
        for tr in self.tracks:
            for i, p in enumerate(frame.persons):
                d = _dist(tr.person.centroid, p.centroid)
                if d <= self.max_dist:
                    pairs.append((d, tr, i))
        pairs.sort(key=lambda x: x[0])

        matched_tracks, matched_persons, results = set(), set(), []
        for d, tr, i in pairs:
            if id(tr) in matched_tracks or i in matched_persons:
                continue
            matched_tracks.add(id(tr))
            matched_persons.add(i)
            person = frame.persons[i]
            speed = centroid_speed(tr.person, tr.t, person, frame.t)
            tr.person, tr.t = person, frame.t
            results.append((tr, person, speed))

        for i, p in enumerate(frame.persons):
            if i not in matched_persons:
                tr = Track(self._next_id, p, frame.t)
                self._next_id += 1
                self.tracks.append(tr)
                results.append((tr, p, None))

        self.tracks = [tr for tr in self.tracks if frame.t - tr.t <= self.ttl]
        return results
