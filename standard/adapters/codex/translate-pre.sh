#!/bin/bash
# Codex PreToolUse → 표준 envelope → pre_tool_use handler.
#
# Codex 입력:
# {
#   "session_id", "transcript_path", "cwd", "model", "hook_event_name": "PreToolUse",
#   "turn_id", "tool_name", "tool_use_id", "tool_input"
# }
#
# 표준 hook 출력: {"decision":"allow|self_correct|hard_stop", "reason":"..."}
#
# Codex 응답 (block 시):
#   {
#     "hookSpecificOutput": {
#       "hookEventName": "PreToolUse",
#       "permissionDecision": "deny",
#       "permissionDecisionReason": "<reason>"
#     }
#   }
# 또는 legacy: {"decision":"block","reason":"..."}
# 또는 exit 2 + stderr.

set -euo pipefail

codex_input="$(cat)"

if command -v jq >/dev/null 2>&1; then
  std_input="$(echo "$codex_input" | jq '{
    hook_type: "pre_tool_use",
    session_id: .session_id,
    project_root: .cwd,
    tool_name: .tool_name,
    tool_args: .tool_input,
    turn_id: .turn_id,
    tool_use_id: .tool_use_id,
    model: .model
  }')"
else
  std_input="$codex_input"
fi

std_output="$(echo "$std_input" | "$HOME/.harness/standard/hooks/pre_tool_use/handler.sh" || true)"

if [[ -z "$std_output" ]]; then
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "$std_output"
  exit 0
fi

decision="$(echo "$std_output" | jq -r '.decision // "allow"')"
reason="$(echo "$std_output" | jq -r '.reason // ""')"

if [[ "$decision" == "allow" ]]; then
  exit 0
fi

# block — codex 의 신 형식
jq -n --arg reason "$reason" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: $reason
  }
}'
