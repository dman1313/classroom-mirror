#!/bin/sh
# Double-click for the V2 camera picker, or pass smoke arguments in Terminal.
set -eu

cd "$(dirname "$0")"
python_bin=".venv-mac-v2/bin/python"

if [ ! -x "$python_bin" ]; then
  echo "The V2 Mac runtime is not installed. Run: ./install-v2-mac.sh"
  exit 2
fi

exec "$python_bin" -m v2_runtime.mac_launcher "$@"
