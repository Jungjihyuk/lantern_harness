#!/bin/bash
# Claude UserPromptSubmit hook → 표준 envelope → user_prompt_submit.sh.
# 가드레일(input filter) 진입점.

set -euo pipefail

claude_input="$(cat)"

if command -v jq >/dev/null 2>&1; then
  std_input="$(echo "$claude_input" | jq '{
    hook_type: "user_prompt_submit",
    session_id: .session_id,
    project_root: .cwd,
    prompt: .prompt
  }')"
else
  std_input="$claude_input"
fi

exec "$HOME/.harness/standard/hooks/user_prompt_submit/user_prompt_submit.sh" <<< "$std_input"
