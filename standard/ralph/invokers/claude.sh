#!/bin/bash
# Claude CLI invoker — claude의 비대화 모드 (--print)로 prompt 전달.
# 단점: hook 발동 여부가 환경별로 다를 수 있음. 시도 실패 시 manual로 fallback 권장.
#
# 인자: <prompt_file> <response_file>

set -euo pipefail

PROMPT_FILE="$1"
RESPONSE_FILE="$2"

if ! command -v claude >/dev/null 2>&1; then
  echo "Error: claude CLI 없음. manual invoker 사용 권장." >&2
  exit 99
fi

# claude의 비대화 모드 시도. -p 또는 --print
PROMPT_TEXT="$(cat "$PROMPT_FILE")"

# 시도 1: claude -p
if claude --help 2>&1 | grep -qE -- "(--print|^\s+-p,)"; then
  echo "$PROMPT_TEXT" | claude -p > "$RESPONSE_FILE" 2>&1
  rc=$?
elif claude --help 2>&1 | grep -q "non-interactive"; then
  # 다른 가능 플래그
  echo "$PROMPT_TEXT" | claude --non-interactive > "$RESPONSE_FILE" 2>&1
  rc=$?
else
  echo "Error: claude CLI에서 비대화 모드 미지원 — manual invoker 사용." >&2
  exit 99
fi

if [[ $rc -ne 0 ]]; then
  echo "Warning: claude 호출 실패 (rc=$rc). 응답 파일 확인:" >&2
  head -5 "$RESPONSE_FILE" >&2
fi

exit $rc
