#!/bin/bash
# post_tool_use handler — 실 logic 은 lib/hooks/post_tool_use.py.

set -euo pipefail

HARNESS_HOME="${HARNESS_HOME:-$HOME/.harness}"

if [[ -d "$HARNESS_HOME/lib/hooks" ]]; then
  LIB_ROOT="$HARNESS_HOME"
else
  LIB_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
fi

export HARNESS_HOME
exec env PYTHONPATH="$LIB_ROOT" python3 -m lib.hooks.post_tool_use
