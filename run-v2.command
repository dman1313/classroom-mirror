#!/bin/sh
# Double-click for the teacher dashboard, or pass smoke arguments in Terminal.
set -eu

cd "$(dirname "$0")"
camera_python=".venv-mac-v2/bin/python"
product_python=".venv/bin/python"

camera_only=0
for arg in "$@"; do
  case "$arg" in
    --smoke-test|--list-cameras) camera_only=1 ;;
  esac
done

if [ "$camera_only" -eq 1 ]; then
  python_bin="$camera_python"
  if [ ! -x "$python_bin" ]; then
    echo "The V2 Mac camera runtime is not installed. Run: ./install-v2-mac.sh"
    exit 2
  fi
else
  if [ -x "$product_python" ]; then
    python_bin="$product_python"
  elif [ -x "$camera_python" ]; then
    python_bin="$camera_python"
  else
    echo "The teacher dashboard needs ./install.sh (YOLO11 pose). Camera smoke only: ./install-v2-mac.sh"
    exit 2
  fi
fi

exec "$python_bin" -m v2_runtime.mac_launcher "$@"
