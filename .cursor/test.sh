#!/usr/bin/env bash
# One command to run the full camera-free validation battery with the correct
# interpreter for each suite. Intended for autonomous iterate -> test loops.
#
#   bash .cursor/test.sh
#
# Exits non-zero if any suite fails. Camera-dependent checks (V2 --stage t1,
# live webcam capture) are intentionally excluded: the Cloud Agent VM has no
# camera and no way to create one (no kernel modules). See .cursor/README.md.
set -uo pipefail

cd "$(dirname "$0")/.."

V1_PY="./.venv/bin/python"
V2_PY="./.venv-mac-v2/bin/python"

if [ ! -x "$V1_PY" ] || [ ! -x "$V2_PY" ]; then
  echo "Virtualenvs are missing. Run: bash .cursor/install.sh" >&2
  exit 1
fi

fail=0
run() {
  local name="$1"; shift
  echo ""
  echo "===== $name ====="
  if "$@"; then
    echo "PASS: $name"
  else
    echo "FAIL: $name"
    fail=1
  fi
}

run "V1 scoreboard (./check)"        "$V1_PY" -m tests.scoreboard
run "V2 readiness (t0)"              "$V2_PY" check-v2.py --stage t0
run "V2 shared/mac acceptance (t1-mac)" "$V2_PY" check-v2.py --stage t1-mac
run "V2 runtime pytest suites"       "$V1_PY" -m pytest v2_tests/ -q

echo ""
echo "======================================"
if [ "$fail" -eq 0 ]; then
  echo "ALL SUITES PASSED"
else
  echo "ONE OR MORE SUITES FAILED"
fi
exit "$fail"
