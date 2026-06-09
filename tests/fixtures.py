"""Synthetic keypoint streams with known ground truth.

Made-up data only — the contract forbids real children's data during
development, so every "person" here is a bundle of coordinates we generate.
"""
from app.heuristics import KeypointFrame, Person

FPS = 5
ZONE = (0.35, 0.25, 0.3, 0.5)  # x, y, w, h — fixture person sits at its center


def make_person(cx=0.5, cy=0.5, h=0.3, wrist_up=False):
    eye_y = cy - 0.38 * h
    up_y = eye_y - 0.15 * h          # clearly above the 0.05*h margin
    down_y = cy + 0.10 * h
    wrist_y = up_y if wrist_up else down_y
    kps = {
        "nose": (cx, eye_y, 0.9),
        "left_eye": (cx - 0.01, eye_y, 0.9),
        "right_eye": (cx + 0.01, eye_y, 0.9),
        "left_wrist": (cx - 0.05, wrist_y, 0.9),
        "right_wrist": (cx + 0.05, down_y, 0.9),
        "left_hip": (cx - 0.03, cy + 0.05 * h, 0.9),
        "right_hip": (cx + 0.03, cy + 0.05 * h, 0.9),
    }
    return Person(kps=kps, bbox=(cx - h / 6, cy - h / 2, h / 3, h))


def stream_three_raises(duration=120.0):
    """One person at the zone center. Real raises (held 1.5 s) at t=10, 40, 80
    plus a 0.2 s flicker at t=60 that must NOT count. Truth: 3 raises."""
    raise_windows = [(10, 11.5), (40, 41.5), (80, 81.5), (60, 60.2)]
    frames = []
    for i in range(int(duration * FPS)):
        t = i / FPS
        up = any(a <= t < b for a, b in raise_windows)
        frames.append(KeypointFrame(t, [make_person(0.5, 0.5, wrist_up=up)]))
    return frames, 3


def stream_away(duration=120.0):
    """Person leaves the room during [30,60) and [90,102).
    Truth per minute: minute 0 -> 50% at spot, minute 1 -> 80%."""
    away = [(30, 60), (90, 102)]
    frames = []
    for i in range(int(duration * FPS)):
        t = i / FPS
        gone = any(a <= t < b for a, b in away)
        persons = [] if gone else [make_person(0.5, 0.5)]
        frames.append(KeypointFrame(t, persons))
    return frames, {0: 50.0, 1: 80.0}


def stream_movement(speed, duration=60.0):
    """Person oscillates horizontally at a constant `speed` in
    body-heights/second. Truth: the movement bucket for that speed."""
    h = 0.3
    dx = speed * h / FPS             # per frame
    frames = []
    cx, direction = 0.5, 1
    for i in range(int(duration * FPS)):
        t = i / FPS
        cx += direction * dx
        if cx > 0.55 or cx < 0.45:
            direction *= -1
            cx = min(max(cx, 0.45), 0.55)
        frames.append(KeypointFrame(t, [make_person(cx, 0.5, h=h)]))
    return frames


def build_mode1_db(db, lims="L-7"):
    """Two baseline + two strategy sessions with clean known numbers.
    Truth: hand raises per 10 min 5.0 -> 15.0; at spot 50% -> 80%;
    movement low -> medium."""
    plan = [("baseline", 50.0, "low", 1), ("baseline", 50.0, "low", 1),
            ("strategy", 80.0, "medium", 3), ("strategy", 80.0, "medium", 3)]
    for phase, pct, bucket, raises in plan:
        sid = db.start_session("mode1", phase, "6B",
                               [{"lims": lims, "zone": ZONE, "consent": True}])
        for minute in (0, 1):
            db.add_mode1_minute(sid, lims, minute, pct, bucket)
        for k in range(raises):
            db.add_mode1_event(sid, lims, 10.0 * k + 5)
        db.end_session(sid)


def build_mode2_db(db):
    """Two whole-class sessions. Truth per session: 2 raises total,
    3 people typical, 2 minutes observed."""
    ids = []
    for _ in range(2):
        sid = db.start_session("mode2", "none", "6B")
        db.add_mode2_minute(sid, 0, 3, 1, "low")
        db.add_mode2_minute(sid, 1, 3, 1, "low")
        db.end_session(sid)
        ids.append(sid)
    return ids


def stream_class(duration=120.0):
    """Three people. The middle one raises a hand at t=20 and t=70 (held
    1.5 s). Everyone otherwise still. Truth: 3 people, 2 raises total,
    movement low in both minutes."""
    raise_windows = [(20, 21.5), (70, 71.5)]
    frames = []
    for i in range(int(duration * FPS)):
        t = i / FPS
        up = any(a <= t < b for a, b in raise_windows)
        persons = [
            make_person(0.2, 0.5, h=0.25),
            make_person(0.5, 0.5, h=0.25, wrist_up=up),
            make_person(0.8, 0.5, h=0.25),
        ]
        frames.append(KeypointFrame(t, persons))
    return frames, {"bodies": 3, "raises": 2, "bucket": "low"}
