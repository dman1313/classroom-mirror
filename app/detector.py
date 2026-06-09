"""Pose detection wrapper. The only file that touches the ML model.

It outputs body keypoints and boxes — nothing else. No face embedding, no
identity, no emotion: the model literally has no such outputs (guardrail 2/3).
Analytics sync is disabled and weights are loaded from a local file, so
nothing is fetched at runtime (guardrail 5).
"""
import os
from typing import List

from .heuristics import Person

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEIGHTS = os.path.join(ROOT, "yolo11n-pose.pt")

COCO_KP_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]


class PoseDetector:
    def __init__(self, weights: str = WEIGHTS):
        if not os.path.exists(weights):
            raise FileNotFoundError(
                "The pose model file is missing. Run the installer first "
                "(see SETUP.md) — it downloads the model once; after that the "
                "app never touches the internet."
            )
        from ultralytics import YOLO, settings
        settings.update({"sync": False})  # no analytics, ever
        self.model = YOLO(weights)

    def detect(self, frame_bgr) -> List[Person]:
        results = self.model.predict(frame_bgr, verbose=False, conf=0.25)
        persons: List[Person] = []
        for r in results:
            if r.keypoints is None or r.boxes is None or len(r.boxes) == 0:
                continue
            kps_all = r.keypoints.xyn.cpu().numpy()      # (n, 17, 2) normalized
            confs_all = (r.keypoints.conf.cpu().numpy()
                         if r.keypoints.conf is not None else None)
            boxes = r.boxes.xyxyn.cpu().numpy()           # (n, 4) normalized
            for i in range(len(boxes)):
                x1, y1, x2, y2 = boxes[i]
                kps = {}
                for j, name in enumerate(COCO_KP_NAMES):
                    x, y = kps_all[i][j]
                    c = float(confs_all[i][j]) if confs_all is not None else 1.0
                    kps[name] = (float(x), float(y), c)
                persons.append(Person(
                    kps=kps,
                    bbox=(float(x1), float(y1), float(x2 - x1), float(y2 - y1)),
                ))
        return persons
