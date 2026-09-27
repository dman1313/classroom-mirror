#!/bin/sh
# Historical V1 entry point. The current product is the teacher dashboard.
cd "$(dirname "$0")" || exit 1
echo "This is the retired V1 Classroom Mirror build."
echo "Use Open Classroom Mirror.command (or ./run-v2.command) for the current product."
echo "See README.md and SDD-DASHBOARD.md."
printf "Press Return to close. "
read -r _
exit 2
