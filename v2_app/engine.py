"""Live session: sticky anonymous IDs, fidget bands, optional hand-raises."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.heuristics import HandRaiseDetector, Person, centroid_speed, hand_is_up

from .alerts import BAND_NONE, AlertState, update_alert
from .identity import IdentityBook, MATCH_FLOOR
from .sensitivity import SensitivityProfile, get_profile


@dataclass
class Detection:
    bbox: tuple[float, float, float, float]
    vector: list[float]
    person: Person | None = None


@dataclass
class TrackedStudent:
    number: int
    bbox: tuple[float, float, float, float]
    last_t: float
    last_person: Person | None
    speed: float | None
    match: float
    alert: AlertState = field(default_factory=AlertState)
    raises: int = 0
    raise_detector: HandRaiseDetector = field(default_factory=HandRaiseDetector)
    hidden: bool = False


@dataclass
class RecapRow:
    number: int
    peak_band: str
    raises: int
    cue: str


class SessionEngine:
    def __init__(self, book: IdentityBook, sensitivity: str):
        self.book = book
        self.profile: SensitivityProfile = get_profile(sensitivity)
        self.locked_profile_key = self.profile.key
        self.students: dict[int, TrackedStudent] = {}
        self.hidden = False
        self.started_at: float | None = None
        self.peak_band: dict[int, str] = {}
        self.room_raises = 0
        self.frames = 0

    def ingest(self, t: float, detections: list[Detection]) -> None:
        if self.started_at is None:
            self.started_at = t
        self.frames += 1
        seen: set[int] = set()
        for det in detections:
            number, score = self.book.match_or_create(det.vector, t)
            if score < MATCH_FLOOR:
                continue
            seen.add(number)
            person = det.person or Person(kps={}, bbox=det.bbox)
            existing = self.students.get(number)
            speed = None
            if existing and existing.last_person is not None:
                speed = centroid_speed(existing.last_person, existing.last_t, person, t)
            if existing is None:
                existing = TrackedStudent(
                    number=number,
                    bbox=det.bbox,
                    last_t=t,
                    last_person=person,
                    speed=speed,
                    match=score,
                )
                self.students[number] = existing
            existing.bbox = det.bbox
            existing.last_t = t
            existing.last_person = person
            existing.speed = speed
            existing.match = score
            update_alert(existing.alert, t, speed, self.profile)
            self._bump_peak(number, existing.alert.band)
            if person.kps and existing.raise_detector.update(t, person):
                existing.raises += 1
                self.room_raises += 1

        stale = [n for n, st in self.students.items() if n not in seen and t - st.last_t > 2.0]
        for n in stale:
            del self.students[n]

    def snapshot(self) -> dict:
        rows = []
        for st in sorted(self.students.values(), key=lambda s: s.number):
            if self.hidden:
                continue
            rows.append(
                {
                    "number": st.number,
                    "band": st.alert.band,
                    "cue": st.alert.label,
                    "raises": st.raises,
                    "match": round(st.match, 3),
                }
            )
        return {
            "running": True,
            "hidden": self.hidden,
            "sensitivity": self.locked_profile_key,
            "profile_version": self.profile.version,
            "students": rows,
            "room_raises": self.room_raises,
            "frames": self.frames,
            "support_copy": "Flags are uncertain movement cues. They are not facts, grades, or discipline.",
        }

    def recap(self) -> dict:
        rows = []
        numbers = sorted(set(self.peak_band) | set(self.students))
        for number in numbers:
            st = self.students.get(number)
            peak = self.peak_band.get(number, BAND_NONE)
            cue = ""
            if peak == "red":
                cue = "possible support needed — sustained movement (uncertain)"
            elif peak == "yellow":
                cue = "possible support needed — more movement than usual (uncertain)"
            rows.append(
                {
                    "number": number,
                    "peak_band": peak,
                    "raises": st.raises if st else 0,
                    "cue": cue,
                }
            )
        return {
            "sensitivity": self.locked_profile_key,
            "profile_version": self.profile.version,
            "room_raises": self.room_raises,
            "students": rows,
            "support_copy": (
                "This recap is for the teacher only. Numbers are anonymous. "
                "Cues are uncertain. They must not be used for grading, attendance, "
                "or an automated consequence."
            ),
        }

    def _bump_peak(self, number: int, band: str) -> None:
        order = {BAND_NONE: 0, "yellow": 1, "red": 2}
        current = self.peak_band.get(number, BAND_NONE)
        if order.get(band, 0) > order.get(current, 0):
            self.peak_band[number] = band
