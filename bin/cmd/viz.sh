#!/bin/bash
# harness viz <type> [options].
#   workflow / subagents / bottleneck → main.py
#   dashboard                          → dashboard.py (라이브 브라우저)

set -euo pipefail

HARNESS_HOME="$HOME/.harness"
VIZ_DIR="$HARNESS_HOME/lib/viz"

if [[ $# -eq 0 ]]; then
  python3 "$VIZ_DIR/main.py" --help 2>&1 | head -20
  echo ""
  echo "  dashboard  [--port N] [--no-open]   라이브 브라우저 대시보드"
  exit 0
fi

vtype="$1"
shift

if [[ "$vtype" == "dashboard" ]]; then
  exec python3 "$VIZ_DIR/dashboard.py" "$@"
else
  exec python3 "$VIZ_DIR/main.py" "$vtype" "$@"
fi
