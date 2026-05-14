#!/bin/bash
# Codex Stop → 표준 envelope → stop handler.
#
# ⚠ 의미 주의: codex 의 Stop "decision: block" 은 *재개* (continuation prompt 자동 생성).
#   claude 의 Stop block (= 종료 차단 / 재시도 유도) 과 의도가 일치하므로 같은 매핑 사용 가능.
#   완전 중단을 원하면 {"continue": false, "stopReason": "..."} 로 응답.
#
# Codex 입력:
# {
#   "session_id", "transcript_path", "cwd", "model", "hook_event_name": "Stop",
#   "turn_id", "stop_hook_active", "last_assistant_message"
# }
#
# 표준 hook 출력:
#   - decision="allow" → 정상 종료 → exit 0
#   - decision="self_correct" → verify 실패 → 재시도 유도 → codex 의 {decision:"block",reason:"..."}
#   - decision="hard_stop" → 절대 중단 → codex 의 {continue: false, stopReason: "..."}

set -euo pipefail

codex_input="$(cat)"

if command -v jq >/dev/null 2>&1; then
  std_input="$(echo "$codex_input" | jq '{
    hook_type: "stop",
    session_id: .session_id,
    project_root: .cwd,
    stop_hook_active: .stop_hook_active,
    last_assistant_message: .last_assistant_message,
    turn_id: .turn_id,
    model: .model
  }')"
else
  std_input="$codex_input"
fi

std_output="$(echo "$std_input" | "$HOME/.harness/standard/hooks/stop/handler.sh" || true)"

if [[ -z "$std_output" ]]; then
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "$std_output"
  exit 0
fi

decision="$(echo "$std_output" | jq -r '.decision // "allow"')"
reason="$(echo "$std_output" | jq -r '.reason // ""')"

case "$decision" in
  allow)
    exit 0
    ;;
  self_correct)
    # 재시도 유도 — codex 가 reason 을 새 user prompt 로 사용해 계속 진행
    jq -n --arg reason "$reason" '{decision: "block", reason: $reason}'
    ;;
  hard_stop)
    # 무조건 중단 — codex 의 자동 continuation override
    jq -n --arg reason "$reason" '{continue: false, stopReason: $reason}'
    ;;
  *)
    exit 0
    ;;
esac
