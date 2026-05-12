#!/bin/bash
# Claude PreToolUse → 표준 envelope 변환 → pre_tool_use.sh 호출 → claude 형식으로 응답.
#
# Claude의 PreToolUse hook 입력 (예시):
# {
#   "session_id": "...",
#   "transcript_path": "...",
#   "cwd": "...",
#   "hook_event_name": "PreToolUse",
#   "tool_name": "Edit",
#   "tool_input": {...}
# }
#
# Claude 응답 포맷:
# { "decision": "allow"|"deny"|"ask", "reason": "..." }

set -euo pipefail

claude_input="$(cat)"

# 표준 envelope로 변환
if command -v jq >/dev/null 2>&1; then
  std_input="$(echo "$claude_input" | jq '{
    hook_type: "pre_tool_use",
    session_id: .session_id,
    project_root: .cwd,
    tool_name: .tool_name,
    tool_args: .tool_input
  }')"
else
  # jq 없으면 그대로 전달 (표준 hook이 같은 키 받음 가정)
  std_input="$claude_input"
fi

# 표준 hook 호출
std_output="$(echo "$std_input" | "$HOME/.harness/standard/hooks/pre_tool_use/handler.sh")"

# Claude 응답 형식 (decision/reason은 동일)
echo "$std_output"
