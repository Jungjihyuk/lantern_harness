#!/bin/bash
# Stuck detection — 같은 path 연속 수정 카운터 검사.
# 인자: project_root threshold
# 종료: 0 = OK (not stuck), 1 = stuck

set -euo pipefail

PROJECT_ROOT="$1"
THRESHOLD="$2"
SESSIONS_DIR="$PROJECT_ROOT/.harness/runtime/sessions"

if [[ ! -d "$SESSIONS_DIR" ]]; then
  exit 0  # 세션 정보 없음 = stuck 아님
fi

# 가장 최근 세션의 cognitive-guard.json edit_history 검사
latest_session="$(ls -t "$SESSIONS_DIR" 2>/dev/null | head -1)"
if [[ -z "$latest_session" ]]; then
  exit 0
fi

guard="$SESSIONS_DIR/$latest_session/cognitive-guard.json"
if [[ ! -f "$guard" ]]; then
  exit 0
fi

if command -v jq >/dev/null 2>&1; then
  # edit_history 끝의 N개가 모두 같은 path면 stuck
  same_count="$(jq -r --argjson n "$THRESHOLD" '
    .edit_history as $h
    | if ($h | length) < $n then 0
      else
        ($h | reverse | .[0:$n] | unique | length)
      end
  ' "$guard")"
  if [[ "$same_count" == "1" ]]; then
    exit 1
  fi
fi

exit 0
