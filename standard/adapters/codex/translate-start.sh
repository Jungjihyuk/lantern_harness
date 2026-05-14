#!/bin/bash
# Codex SessionStart → 표준 envelope → session_start handler.
#
# Codex 의 SessionStart hook 입력 (예시):
# {
#   "session_id": "...",
#   "transcript_path": "...",
#   "cwd": "...",
#   "hook_event_name": "SessionStart",
#   "model": "...",
#   "source": "startup" | "resume" | "clear"
# }
#
# 표준 session_start handler 가 compose 합성 + AGENTS.md 생성 + state init + trace 까지 처리.
# Codex 는 프로젝트 루트의 AGENTS.md 를 native 로 읽으므로, handler 가 만든
# runtime/AGENTS.resolved.md → <project>/AGENTS.md symlink 가 자동 prefix 주입 역할.
#
# 응답:
#   - exit 0 + (선택) hookSpecificOutput.additionalContext = 추가 dev context
#   - 본 어댑터는 단순히 표준 handler 의 출력을 pass-through (대부분 {"decision":"allow"})

set -euo pipefail

codex_input="$(cat)"

if command -v jq >/dev/null 2>&1; then
  std_input="$(echo "$codex_input" | jq '{
    hook_type: "session_start",
    session_id: .session_id,
    project_root: .cwd,
    transcript_path: .transcript_path,
    source: .source,
    model: .model
  }')"
else
  std_input="$codex_input"
fi

# 표준 handler 호출. session_start 는 일반적으로 block 하지 않으므로 pass-through.
exec "$HOME/.harness/standard/hooks/session_start/handler.sh" <<< "$std_input"
