"""Offline pose pipeline. Camera images and keypoints are RAM-only."""

import os
from pathlib import Path

from app.heuristics import Person
from app.detector import COCO_KP_NAMES

ROOT = Path(__file__).resolve().parents[1]


def configure_local_runtime():
    config = ROOT / "data" / "model-config"
    config.mkdir(parents=True, exist_ok=True)
    os.environ["YOLO_OFFLINE"] = "true"
    os.environ["YOLO_AUTOINSTALL"] = "false"
    os.environ["YOLO_CONFIG_DIR"] = str(ROOT / "data" / "model-config")
    os.environ["MPLCONFIGDIR"] = str(ROOT / "data" / "model-config")


class PoseVision:
    def __init__(self):
        weights = ROOT / "yolo11n-pose.pt"
        if not weights.is_file():
            raise RuntimeError(
                "The local pose model is missing. Run Install Classroom Mirror.command once, then try again."
            )
        configure_local_runtime()
        from ultralytics import YOLO, settings

        settings.update({"sync": False})
        self.model = YOLO(str(weights), task="pose")

    def detect(self, frame):
        results = self.model.predict(
            frame,
            verbose=False,
            conf=0.4,
            imgsz=640,
            device="cpu",
            save=False,
            save_txt=False,
            save_crop=False,
            show=False,
            max_det=40,
        )
        persons = []
        for r in results:
            if r.keypoints is None or r.boxes is None:
                continue
            points = r.keypoints.xyn.cpu().numpy()
            confs = r.keypoints.conf.cpu().numpy()
            boxes = r.boxes.xyxyn.cpu().numpy()
            for box, kps, confidence in zip(boxes, points, confs):
                x1, y1, x2, y2 = map(float, box)
                if y2 - y1 < 0.08:
                    continue
                persons.append(
                    Person(
                        {
                            name: (float(p[0]), float(p[1]), float(c))
                            for name, p, c in zip(COCO_KP_NAMES, kps, confidence)
                        },
                        (x1, y1, x2 - x1, y2 - y1),
                    )
                )
        return persons
