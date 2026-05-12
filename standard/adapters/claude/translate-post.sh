#!/bin/bash
# Claude PostToolUse → 표준 envelope → post_tool_use.sh.

set -euo pipefail

claude_input="$(cat)"

if command -v jq >/dev/null 2>&1; then
  std_input="$(echo "$claude_input" | jq '{
    hook_type: "post_tool_use",
    session_id: .session_id,
    project_root: .cwd,
    tool_name: .tool_name,
    tool_args: .tool_input,
    duration_ms: (.duration_ms // 0)
  }')"
else
  std_input="$claude_input"
fi

std_output="$(echo "$std_input" | "$HOME/.harness/standard/hooks/post_tool_use/post_tool_use.sh")"
echo "$std_output"
