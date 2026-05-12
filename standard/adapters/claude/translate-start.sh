#!/bin/bash
# Claude SessionStart → 표준 envelope → session_start.sh.

set -euo pipefail

claude_input="$(cat)"

if command -v jq >/dev/null 2>&1; then
  std_input="$(echo "$claude_input" | jq '{
    hook_type: "session_start",
    session_id: .session_id,
    project_root: .cwd,
    transcript_path: .transcript_path
  }')"
else
  std_input="$claude_input"
fi

std_output="$(echo "$std_input" | "$HOME/.harness/standard/hooks/session_start/handler.sh")"
echo "$std_output"
