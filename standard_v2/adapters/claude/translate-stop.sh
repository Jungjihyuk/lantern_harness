#!/bin/bash
# Claude Stop hook → 표준 envelope → stop.sh.
# Claude는 응답 종료 시점에 Stop hook 발동.
# stop.sh가 exit 2 반환 시 claude는 계속 작업 (verify 실패 → 재시도 유도).

set -euo pipefail

claude_input="$(cat)"

if command -v jq >/dev/null 2>&1; then
  std_input="$(echo "$claude_input" | jq '{
    hook_type: "stop",
    session_id: .session_id,
    project_root: .cwd
  }')"
else
  std_input="$claude_input"
fi

# stop.sh의 exit code 그대로 전파 (2 = block/재시도, 0 = allow)
exec "$HOME/.harness/standard/hooks/stop.sh" <<< "$std_input"
