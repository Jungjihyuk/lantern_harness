#!/bin/bash
# pre_tool_use handler — 도구 호출 직전 다중 가드.
#
# 처리 (deny 우선):
#   1. path_blocklist  — sensitive path 차단 (모든 도구)
#   2. required_check  — Required Context 미읽음 (변경 도구만)
#   3. context_gating  — triggered 매칭 + doc 미읽음
#   4. cognitive_guard — per_call / per_session 초과 (bypass marker 시 skip)
#   5. loop_detection  — state.workflows 에 ralph 등록 시 자동 활성
#   6. trace_log       — 결정 무관 기록
#
# stdin: 표준 envelope JSON (tool_name + tool_args 포함)
# stdout: {"decision":"allow|self_correct|hard_stop","reason":"..."}
#
# 실 logic 은 lib/hooks/pre_tool_use.py.

set -euo pipefail

HARNESS_HOME="${HARNESS_HOME:-$HOME/.harness}"

if [[ -d "$HARNESS_HOME/lib/hooks" ]]; then
  LIB_ROOT="$HARNESS_HOME"
else
  LIB_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
fi

export HARNESS_HOME
exec env PYTHONPATH="$LIB_ROOT" python3 -m lib.hooks.pre_tool_use
