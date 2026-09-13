#!/bin/sh
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv-mac-v2/bin/python ]; then
  echo 'First double-click Install Classroom Mirror.command in this folder.'
  printf 'Press Return to close. '
  read -r classroom_answer
  exit 2
fi
./run-v2.command "$@"
classroom_result=$?
if [ "$classroom_result" -ne 0 ]; then
  printf 'Press Return to close. '
  read -r classroom_answer
fi
exit "$classroom_result"
