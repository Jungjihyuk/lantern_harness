#!/bin/bash
# session_start handler — 세션 시작 시 AGENTS.md 합성 + state 초기화 + trace.
#
# 책임 (manifest 의 roles):
#   - prefix_injection: compose cognition entries 합성 → runtime/AGENTS.resolved.md
#   - status_init:      runtime/sessions/<id>/ 상태 파일 초기화
#   - trace_log:        session_start 이벤트 기록
#
# stdin: 표준 envelope JSON
#   {"hook_type":"session_start","session_id":"...","project_root":"...","transcript_path":"..."}
#
# stdout: {"decision":"allow"}
#
# 실 logic 은 lib/hooks/session_start.py.

set -euo pipefail

HARNESS_HOME="${HARNESS_HOME:-$HOME/.harness}"

# install 된 lib 우선, 없으면 dev fallback
if [[ -d "$HARNESS_HOME/lib/hooks" ]]; then
  LIB_ROOT="$HARNESS_HOME"
else
  LIB_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
fi

export HARNESS_HOME
exec env PYTHONPATH="$LIB_ROOT" python3 -m lib.hooks.session_start
