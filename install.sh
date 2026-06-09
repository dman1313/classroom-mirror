#!/bin/sh
# One-time setup. Needs the internet ONCE (to fetch the app's building blocks
# and the pose model). After this, the app never touches the internet.
set -e
cd "$(dirname "$0")"
echo "1/3 Creating a private Python environment in this folder..."
python3 -m venv .venv
echo "2/3 Installing the app's building blocks (this is the slow part)..."
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements.txt
echo "3/3 Downloading the pose model (one time only)..."
./.venv/bin/python -c "
from ultralytics import YOLO, settings
settings.update({'sync': False})
YOLO('yolo11n-pose.pt')
print('Model ready.')
"
echo
echo "Done. Double-click run.command to start, or run ./check to verify."
