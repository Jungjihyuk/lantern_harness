#!/bin/bash
# user_prompt_submit (Claude: UserPromptSubmit)
# 역할:
#   1. prompt 저장 (prompts.jsonl) — 헤맴 추적·improve 분석용
#   2. 가드레일 (input filter) — 미래 확장 자리

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

input="$(cat)"
session_id="$(echo "$input" | json_get 'session_id')"
project_root="$(echo "$input" | json_get 'project_root')"
prompt="$(echo "$input" | json_get 'prompt')"
[[ -z "$project_root" ]] && project_root="$PWD"
export HARNESS_PROJECT_ROOT="$project_root"

# 안전 가드: .harness/ 없으면 즉시 통과
if [[ ! -d "$project_root/.harness" ]]; then
  json_response "allow"
fi

# Prompt 저장 (분석용)
if [[ -n "$prompt" ]]; then
  pf="$(session_dir "$project_root" "$session_id")/prompts.jsonl"
  ts="$(date -u +%Y-%m-%dT%H:%M:%S.%NZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)"
  if command -v jq >/dev/null 2>&1; then
    jq -nc --arg ts "$ts" --arg sid "$session_id" --arg p "$prompt" \
      '{ts: $ts, session_id: $sid, prompt: $p}' >> "$pf"
  fi
fi

# Trace 기록 (workflow viz의 user_prompt_submit 카운트용)
ts2="$(date -u +%Y-%m-%dT%H:%M:%S.%NZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)"
trace_evt=$(printf '{"ts":"%s","session_id":"%s","event_type":"user_prompt_submit"}' "$ts2" "$session_id")
trace_append "$project_root" "$session_id" "$trace_evt"

# TODO: 미래 가드레일 룰 (regex·LLM-judge) — 현재 통과
json_response "allow"
