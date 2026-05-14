#!/bin/bash
# Codex UserPromptSubmit → 표준 envelope → user_prompt_submit handler.
#
# Codex 입력:
# {
#   "session_id", "transcript_path", "cwd", "model", "hook_event_name": "UserPromptSubmit",
#   "turn_id", "prompt"
# }
#
# 응답:
#   - decision="allow": exit 0
#   - decision="self_correct"|"hard_stop": exit 2 + stderr 에 reason (codex 가 block 으로 해석)
#   - 또는 stdout 에 {"decision":"block","reason":"..."} JSON (codex 의 legacy 형식)

set -euo pipefail

codex_input="$(cat)"

if command -v jq >/dev/null 2>&1; then
  std_input="$(echo "$codex_input" | jq '{
    hook_type: "user_prompt_submit",
    session_id: .session_id,
    project_root: .cwd,
    prompt: .prompt,
    turn_id: .turn_id,
    model: .model
  }')"
else
  std_input="$codex_input"
fi

# user_prompt_submit handler 가 없을 수 있음 — 안전하게 처리
HANDLER="$HOME/.harness/standard/hooks/user_prompt_submit/handler.sh"
if [[ ! -x "$HANDLER" ]]; then
  exit 0
fi

std_output="$(echo "$std_input" | "$HANDLER" || true)"

if [[ -z "$std_output" ]]; then
  exit 0
fi

if command -v jq >/dev/null 2>&1; then
  decision="$(echo "$std_output" | jq -r '.decision // "allow"')"
  reason="$(echo "$std_output" | jq -r '.reason // ""')"
else
  decision="allow"
  reason=""
fi

if [[ "$decision" == "allow" ]]; then
  exit 0
fi

# block — codex legacy 형식
jq -n --arg reason "$reason" '{decision: "block", reason: $reason}'
