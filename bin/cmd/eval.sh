#!/bin/bash
# harness eval — 실 logic 은 lib/eval/main.py (또는 lib/eval/runner.py).

set -euo pipefail

HARNESS_HOME="${HARNESS_HOME:-$HOME/.harness}"

if [[ -d "$HARNESS_HOME/lib/eval" ]]; then
  LIB_ROOT="$HARNESS_HOME"
else
  LIB_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
fi

export HARNESS_HOME
exec env PYTHONPATH="$LIB_ROOT" python3 -m lib.eval.runner "$@"
