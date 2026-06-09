#!/bin/sh
# Double-click me to start Classroom Mirror. It opens in your web browser.
cd "$(dirname "$0")"
if [ ! -x ".venv/bin/python" ]; then
  echo "The app is not installed yet. Run:  bash install.sh"
  read -r _
  exit 1
fi
echo "Starting Classroom Mirror at http://127.0.0.1:8470 ..."
echo "(Leave this window open. Close it or press Ctrl+C to stop the app.)"
exec ./.venv/bin/python -m app.main
