#!/bin/bash
# harness reload — runtime/AGENTS.resolved.md 강제 재생성.
set -euo pipefail

HARNESS_HOME="$HOME/.harness"
PROJECT_ROOT="$(pwd)"

if [[ ! -d "$PROJECT_ROOT/.harness" ]]; then
  echo "Error: .harness/ 없음" >&2
  exit 1
fi

# session_start를 dummy session id로 호출
sid="reload-$(date +%s)"
echo "{\"hook_type\":\"session_start\",\"session_id\":\"$sid\",\"project_root\":\"$PROJECT_ROOT\"}" \
  | "$HARNESS_HOME/standard/hooks/session_start/session_start.sh"

echo "✓ runtime/AGENTS.resolved.md 재생성"
