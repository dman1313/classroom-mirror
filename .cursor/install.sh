#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for Classroom Mirror.
#
# The personal environment's install command is `.cursor/install.sh`. That file
# was never merged to main, so recurring builds failed with "No such file or
# directory". This script is self-contained: it uses the default image's
# python3 (not a Dockerfile-only python3.11) and does not depend on other
# files under .cursor/.
set -euo pipefail

if [ -f requirements.txt ]; then
  ROOT="$PWD"
elif [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "$(dirname "${BASH_SOURCE[0]}")/../requirements.txt" ]; then
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
else
  ROOT="/workspace"
fi
cd "$ROOT"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python3.11 >/dev/null 2>&1; then
  PY=python3.11
else
  echo "FAIL: python3 is required but was not found on PATH." >&2
  exit 1
fi

echo "== V1 pose stack (app/, tests/) =="
"$PY" -m venv .venv
./.venv/bin/python -m pip install --disable-pip-version-check --quiet --upgrade pip
./.venv/bin/python -m pip install --disable-pip-version-check --quiet -r requirements.txt
echo "Fetching the pose model if it is not already present..."
./.venv/bin/python - <<'PYEOF'
from ultralytics import YOLO, settings
settings.update({"sync": False})
YOLO("yolo11n-pose.pt")
print("Pose model ready.")
PYEOF

echo "== V2 camera runtime (v2_runtime/) =="
"$PY" -m venv .venv-mac-v2
./.venv-mac-v2/bin/python -m pip install --disable-pip-version-check --quiet --upgrade pip
./.venv-mac-v2/bin/python -m pip install --disable-pip-version-check --quiet -r requirements-v2-runtime.txt
./.venv-mac-v2/bin/python -c 'import cv2, fastapi, uvicorn; print("V2 runtime imports ready:", cv2.__version__)'

echo "Install complete."
