#!/bin/bash
# Codex PermissionRequest → 표준 envelope → permission_request handler.
#
# Codex 입력:
# {
#   "session_id", "transcript_path", "cwd", "model", "hook_event_name": "PermissionRequest",
#   "turn_id", "tool_name", "tool_input" (+ "tool_input.description" 있을 수 있음)
# }
#
# Codex 응답:
#   승인: {"hookSpecificOutput":{"hookEventName":"PermissionRequest","decision":{"behavior":"allow"}}}
#   거부: {"hookSpecificOutput":{"hookEventName":"PermissionRequest","decision":{"behavior":"deny","message":"..."}}}
#   결정 안 함 (= 기본 승인 flow 계속): exit 0, 본문 없음
#
# 여러 hook 응답 중 deny 가 우선. allow 가 하나라도 있으면 codex 의 승인 prompt 건너뜀.

set -euo pipefail

codex_input="$(cat)"

if command -v jq >/dev/null 2>&1; then
  std_input="$(echo "$codex_input" | jq '{
    hook_type: "permission_request",
    session_id: .session_id,
    project_root: .cwd,
    tool_name: .tool_name,
    tool_args: .tool_input,
    description: .tool_input.description,
    turn_id: .turn_id,
    model: .model
  }')"
else
  std_input="$codex_input"
fi

HANDLER="$HOME/.harness/standard/hooks/permission_request/handler.sh"
if [[ ! -x "$HANDLER" ]]; then
  exit 0
fi

std_output="$(echo "$std_input" | "$HANDLER" || true)"

if [[ -z "$std_output" ]]; then
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "$std_output"
  exit 0
fi

decision="$(echo "$std_output" | jq -r '.decision // ""')"
reason="$(echo "$std_output" | jq -r '.reason // ""')"

case "$decision" in
  allow)
    jq -n '{
      hookSpecificOutput: {
        hookEventName: "PermissionRequest",
        decision: {behavior: "allow"}
      }
    }'
    ;;
  deny|self_correct|hard_stop)
    jq -n --arg msg "$reason" '{
      hookSpecificOutput: {
        hookEventName: "PermissionRequest",
        decision: {behavior: "deny", message: $msg}
      }
    }'
    ;;
  *)
    # 결정 안 함 — codex 의 기본 승인 flow 진행
    exit 0
    ;;
esac
