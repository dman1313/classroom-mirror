# Runtime dependency and model record

Reviewed on 2026-09-13 using installed package metadata and upstream documentation.

| Component | Version | Upstream license metadata |
|---|---|---|
| Ultralytics | 8.4.150 | AGPL-3.0 |
| PyTorch | 2.14.0 | Apache/BSD/MIT and bundled component licenses |
| Torchvision | 0.29.0 | BSD |
| OpenCV Python | 4.14.0.94 | Apache 2.0 |
| NumPy | 2.4.6 | BSD and bundled component licenses |
| FastAPI | 0.141.1 | MIT |
| Uvicorn | 0.52.4 | BSD-3-Clause |

`requirements-dashboard.txt` contains exact dependency versions and SHA-256
hashes for the tested Python 3.11 environment. The installer uses
`pip --require-hashes`. It was resolved and installed on macOS arm64; other
platforms require their own installation/hardware validation.

The retained YOLO11n pose weights come from the official Ultralytics assets
release: https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n-pose.pt

SHA-256: `869e83fcdffdc7371fa4e34cd8e51c838cc729571d1635e5141e3075e9319dc0`

The setup script verifies the download before replacing the local weights.
Weights are not committed to the repository. The software and model retain their
upstream licenses, including the Ultralytics AGPL terms; this is not a
relicensing of the upstream components.

Technical references:
- https://docs.ultralytics.com/tasks/pose/
- https://docs.ultralytics.com/modes/predict/
- https://github.com/ultralytics/ultralytics/blob/main/LICENSE
