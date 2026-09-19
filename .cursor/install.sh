#!/usr/bin/env bash
# Idempotent repository bootstrap for Classroom Mirror Cloud Agents.
#
# Recreates the two project-local virtual environments the codebase uses and
# fetches the one-time pose model. Safe to run repeatedly: venv creation reuses
# an existing environment, pip installs converge, and the model is only
# downloaded when it is missing. System packages (Python 3.11, OpenCV runtime
# libraries) come from .cursor/Dockerfile, not from here.
set -euo pipefail

cd "$(dirname "$0")/.."

PY="${CLASSROOM_MIRROR_PYTHON:-python3.11}"

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "FAIL: $PY is required but was not found on PATH." >&2
  exit 1
fi

echo "== V1 pose stack (app/, tests/) =="
"$PY" -m venv .venv
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements.txt
./.venv/bin/pip install --quiet -r .cursor/requirements-dev.txt
echo "Fetching the pose model if it is not already present..."
./.venv/bin/python - <<'PYEOF'
from ultralytics import YOLO, settings
settings.update({"sync": False})  # no analytics, ever (guardrail 5)
YOLO("yolo11n-pose.pt")
print("Pose model ready.")
PYEOF

echo "== V2 camera runtime (v2_runtime/) =="
"$PY" -m venv .venv-mac-v2
./.venv-mac-v2/bin/pip install --quiet --upgrade pip
./.venv-mac-v2/bin/pip install --quiet -r requirements-v2-runtime.txt
./.venv-mac-v2/bin/pip install --quiet -r .cursor/requirements-dev.txt
./.venv-mac-v2/bin/python -c 'import cv2, fastapi, uvicorn; print("V2 runtime imports ready:", cv2.__version__)'

echo "Install complete."
