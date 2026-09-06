#!/bin/sh
# Double-click to open the Classroom Mirror V2 movement dashboard (adult alpha).
# Choose the camera and High/Low sensitivity on the Start screen in the browser.
set -eu

cd "$(dirname "$0")"
python_bin=".venv-mac-v2/bin/python"

if [ ! -x "$python_bin" ]; then
  echo "The V2 Mac runtime is not installed. Run: ./install-v2-mac.sh"
  exit 2
fi

exec "$python_bin" -m v2_runtime.dashboard "$@"
