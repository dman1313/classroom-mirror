"""Geometry-only, session-local tracking. No biometric matching or templates."""

from dataclasses import dataclass, field
import math

from app.heuristics import Person, HandRaiseDetector


@dataclass(frozen=True)
class Profile:
    yellow: float
    red: float
    recover: float
    threshold: float = 0.12


PROFILES = {"low": Profile(8, 16, 4), "high": Profile(3, 7, 2)}
PROFILE_VERSION = "2026-09-position-1"


@dataclass
class Track:
    number: int
    person: Person
    seen: float
    band: str = "calm"
    moving: bool = False
    above: float | None = None
    below: float | None = None
    yellow_at: float | None = None
    raises: int = 0
    hand: HandRaiseDetector = field(default_factory=HandRaiseDetector)


def movement(previous, current, dt):
    """Body/limb displacement in body heights per second; gaps are unknown."""
    if dt <= 0 or dt > 0.75:
        return None
    h = max(0.1, (previous.height + current.height) / 2)
    speeds = [math.dist(previous.centroid, current.centroid) / h / dt]
    for name in ("left_wrist", "right_wrist", "left_shoulder", "right_shoulder"):
        a, b = previous.kps.get(name), current.kps.get(name)
        if a and b and min(a[2], b[2]) >= 0.5:
            speeds.append(math.dist(a[:2], b[:2]) / h / dt)
    # Ignore single-point keypoint jumps; use the median visible movement.
    return sorted(speeds)[len(speeds) // 2]


class Engine:
    def __init__(self, sensitivity="low"):
        if sensitivity not in PROFILES:
            raise ValueError("Choose Low or High sensitivity.")
        self.sensitivity = sensitivity
        self.profile = PROFILES[sensitivity]
        self.tracks = {}
        self.next_id = 1
        self.frames = self.raises = self.peak = self.yellow_events = self.red_events = 0
        self.timeline = []
        self.last_t = None
        self.visible = []

    def update(self, t, persons):
        if not math.isfinite(t) or (self.last_t is not None and t <= self.last_t):
            raise ValueError("Frame timestamps must increase.")
        self.last_t = t
        self.frames += 1
        # Expire before matching so returning positions cannot inherit stale state.
        self.tracks = {n: tr for n, tr in self.tracks.items() if t - tr.seen <= 1.5}
        candidates = []
        for n, tr in self.tracks.items():
            for i, p in enumerate(persons):
                distance = math.dist(tr.person.centroid, p.centroid)
                if distance <= min(0.18, max(0.06, tr.person.height * 0.35)):
                    candidates.append((distance, n, i))
        assigned, used = {}, set()
        for _, n, i in sorted(candidates):
            if n not in used and i not in assigned:
                assigned[i] = n
                used.add(n)
        visible = []
        for i, p in enumerate(persons):
            n = assigned.get(i)
            if n is None:
                n = self.next_id
                self.next_id += 1
                tr = Track(n, p, t)
                self.tracks[n] = tr
                speed = None
            else:
                tr = self.tracks[n]
                gap = t - tr.seen
                speed = movement(tr.person, p, gap)
                if gap > 0.75:
                    tr.above = tr.below = tr.yellow_at = None
                    tr.band = "calm"
                    tr.hand.update(t, None)
            self._alert(tr, t, speed)
            if tr.hand.update(t, p):
                tr.raises += 1
                self.raises += 1
            tr.person, tr.seen = p, t
            visible.append(tr)
        self.visible = visible
        self.peak = max(self.peak, len(visible))
        bucket = int(t // 10)
        if not self.timeline or self.timeline[-1]["bucket"] != bucket:
            self.timeline.append(
                {"bucket": bucket, "people": len(visible), "moving": 0}
            )
            self.timeline = self.timeline[-1080:]
        self.timeline[-1]["people"] = max(self.timeline[-1]["people"], len(visible))
        self.timeline[-1]["moving"] = max(
            self.timeline[-1]["moving"], sum(tr.moving for tr in visible)
        )

    def _alert(self, tr, t, speed):
        tr.moving = speed is not None and speed >= self.profile.threshold
        if tr.moving:
            tr.below = None
            if tr.above is None:
                tr.above = t
            if tr.band == "calm" and t - tr.above >= self.profile.yellow:
                tr.band, tr.yellow_at = "yellow", t
                self.yellow_events += 1
            elif tr.band == "yellow":
                if tr.yellow_at is None:
                    tr.yellow_at = t
                if t - tr.yellow_at >= self.profile.red:
                    tr.band = "red"
                    self.red_events += 1
        else:
            tr.above = tr.yellow_at = None
            if tr.below is None:
                tr.below = t
            if t - tr.below >= self.profile.recover:
                tr.band = "calm"

    def snapshot(self):
        return {
            "people": len(self.visible),
            "moving": sum(tr.moving for tr in self.visible),
            "raises": self.raises,
            "frames": self.frames,
            "yellow": sum(tr.band == "yellow" for tr in self.visible),
            "red": sum(tr.band == "red" for tr in self.visible),
            "tracks": [
                {
                    "number": tr.number,
                    "bbox": tr.person.bbox,
                    "band": tr.band,
                    "moving": tr.moving,
                    "raises": tr.raises,
                    "keypoints": {
                        k: list(v) for k, v in tr.person.kps.items() if v[2] >= 0.5
                    },
                }
                for tr in self.visible
            ],
            "timeline": [dict(row) for row in self.timeline],
        }

    def recap(self):
        # Store aggregates only, never per-person coordinates or numbers.
        return {
            "peak_people": self.peak,
            "raises": self.raises,
            "frames": self.frames,
            "yellow_events": self.yellow_events,
            "red_events": self.red_events,
            "sensitivity": self.sensitivity,
            "profile_version": PROFILE_VERSION,
            "timeline": [dict(row) for row in self.timeline],
        }
