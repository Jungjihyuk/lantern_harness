#!/bin/bash
# harness dashboard — n8n 스타일 시각 편집기 (localhost web UI).
#
# 사용:
#   harness dashboard [--port 8766] [--no-open] [--reload]
#
# 첫 실행 시 fastapi/uvicorn/pydantic deps 필요. 미설치 시 안내.

set -euo pipefail

HARNESS_HOME="${HARNESS_HOME:-$HOME/.harness}"

if [[ -d "$HARNESS_HOME/lib/dashboard" ]]; then
  LIB_ROOT="$HARNESS_HOME"
else
  LIB_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
fi

export HARNESS_HOME
exec env PYTHONPATH="$LIB_ROOT" python3 -m lib.dashboard.server "$@"
