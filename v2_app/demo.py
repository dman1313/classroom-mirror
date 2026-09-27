"""Made-up keypoints, never a substitute for a real-camera validation."""

import math
from app.heuristics import Person


def demo_people(t):
    people = []
    for i, (x, y) in enumerate(
        (
            (0.13, 0.2),
            (0.41, 0.2),
            (0.69, 0.2),
            (0.13, 0.57),
            (0.41, 0.57),
            (0.69, 0.57),
        )
    ):
        # Long smooth motion produces visible yellow -> red transitions.
        dx = (
            0.035 * math.sin(t * 3)
            if i in (1, 4) and t % 50 < 36
            else 0.001 * math.sin(t)
        )
        x += dx
        if i in (1, 4) and t % 50 < 36:
            y += 0.035 * math.cos(t * 3)
        w, h = 0.14, 0.30
        points = {
            "nose": (x + w / 2, y + 0.04, 1),
            "left_eye": (x + 0.06, y + 0.035, 1),
            "right_eye": (x + 0.08, y + 0.035, 1),
            "left_shoulder": (x + 0.03, y + 0.09, 1),
            "right_shoulder": (x + 0.11, y + 0.09, 1),
            "left_hip": (x + 0.04, y + 0.20, 1),
            "right_hip": (x + 0.10, y + 0.20, 1),
            "left_knee": (x + 0.04, y + 0.25, 1),
            "right_knee": (x + 0.10, y + 0.25, 1),
            "left_ankle": (x + 0.035, y + 0.29, 1),
            "right_ankle": (x + 0.105, y + 0.29, 1),
            "left_elbow": (x + 0.01, y + 0.14, 1),
            "right_elbow": (x + 0.13, y + 0.14, 1),
            "left_wrist": (x + 0.01, y + 0.19, 1),
            "right_wrist": (x + 0.13, y + 0.19, 1),
        }
        if i == 2 and 4 < t % 12 < 6:
            points["right_wrist"] = (x + 0.13, y - 0.035, 1)
            points["right_elbow"] = (x + 0.14, y + 0.035, 1)
        people.append(Person(points, (x, y, w, h)))
    return people
