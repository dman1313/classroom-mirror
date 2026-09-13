#!/bin/sh
cd "$(dirname "$0")" || exit 1
./install-v2-mac.sh
classroom_result=$?
if [ "$classroom_result" -eq 0 ]; then
  echo 'Ready. Double-click Open Classroom Mirror.command to begin.'
fi
printf 'Press Return to close. '
read -r classroom_answer
exit "$classroom_result"
