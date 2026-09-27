#!/bin/sh
# Classroom Mirror teacher dashboard installer for macOS. No sudo/elevation.
set -eu

cd "$(dirname "$0")"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "FAIL: install-v2-mac.sh runs only on macOS."
  exit 2
fi

python_bin="${CLASSROOM_MIRROR_PYTHON:-python3.11}"
if ! command -v "$python_bin" >/dev/null 2>&1; then
  echo "FAIL: Python 3.11 is required. Install it for the current user, then retry."
  exit 2
fi

if ! "$python_bin" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)'; then
  echo "FAIL: $python_bin must be Python 3.11."
  exit 2
fi

echo "Classroom Mirror V2 macOS preflight"
echo "  os=macOS"
echo "  architecture=$(uname -m)"
echo "  python=$($python_bin --version 2>&1)"
echo "  environment=.venv-mac-v2 (project-local, no administrator rights)"
echo "  service=127.0.0.1 only"
echo "  camera=permission requested on first run; frames stay in memory"

if [ "${1:-}" = "--check-only" ]; then
  echo "PASS: preflight only; nothing installed."
  exit 0
fi

if [ "$#" -ne 0 ]; then
  echo "Usage: ./install-v2-mac.sh [--check-only]"
  exit 2
fi

venv_dir=".venv-mac-v2"
echo "Creating the V2 Python environment..."
"$python_bin" -m venv "$venv_dir"
echo "Installing the pinned teacher dashboard runtime..."
"$venv_dir/bin/python" -m pip install --disable-pip-version-check \
  --require-hashes -r requirements-dashboard.txt
"$venv_dir/bin/python" -c 'import cv2, fastapi, uvicorn; print("PASS: V2 runtime imports are ready.")'
"$venv_dir/bin/python" scripts/setup_model.py

echo "Install complete. Double-click Open Classroom Mirror.command."
echo "If macOS asks, allow Terminal in System Settings > Privacy & Security > Camera."
