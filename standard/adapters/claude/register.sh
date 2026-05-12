#!/bin/bash
# Claude Code의 프로젝트 .claude/settings.local.json에 표준 hook entry를 자동 등록.
# 글로벌 ~/.claude/settings.json은 건드리지 않음.
#
# 옵션:
#   --dry-run    실제 파일 수정 없이 미리보기만 출력
#   --global     (위험) ~/.claude/settings.json에 글로벌 등록 — 명시적 옵트인

set -euo pipefail

PROJECT_ROOT="$(pwd)"
HARNESS_HOME="$HOME/.harness"
ADAPTER_DIR="$HARNESS_HOME/standard/adapters/claude"

# 옵션 파싱
DRY_RUN=0
SCOPE="project"
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --global)  SCOPE="global" ;;
    --project) SCOPE="project" ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

# 대상 settings 파일 결정
if [[ "$SCOPE" == "global" ]]; then
  SETTINGS="$HOME/.claude/settings.json"
  echo "⚠ 글로벌 등록 모드 — 모든 claude 세션·모든 프로젝트에 영향"
else
  SETTINGS="$PROJECT_ROOT/.claude/settings.local.json"
  echo "프로젝트 로컬 등록 — $PROJECT_ROOT 만 영향"
  if [[ ! -d "$PROJECT_ROOT/.harness" ]]; then
    echo "⚠ 경고: $PROJECT_ROOT/.harness/ 없음. 'harness init' 먼저 실행 권장."
  fi
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq required" >&2
  exit 1
fi

# 디렉토리·파일 생성은 실제 실행 시에만
if [[ $DRY_RUN -eq 0 ]]; then
  mkdir -p "$(dirname "$SETTINGS")"
  if [[ ! -f "$SETTINGS" ]]; then
    echo '{}' > "$SETTINGS"
  fi
fi

# 현재 settings 읽기 (없으면 빈 객체)
current="$(cat "$SETTINGS" 2>/dev/null || echo '{}')"

# 우리 hook entry로 병합 (우리 command path와 일치하는 기존 entry는 제거 후 추가)
merged="$(echo "$current" | jq \
  --arg pre "$ADAPTER_DIR/translate-pre.sh" \
  --arg post "$ADAPTER_DIR/translate-post.sh" \
  --arg start "$ADAPTER_DIR/translate-start.sh" \
  --arg stop "$ADAPTER_DIR/translate-stop.sh" '
  .hooks //= {}
  | .hooks.PreToolUse //= []
  | .hooks.PostToolUse //= []
  | .hooks.SessionStart //= []
  | .hooks.Stop //= []
  | .hooks.PreToolUse  |= ([{matcher: "Edit|Write|NotebookEdit|MultiEdit|Bash|Read|Grep|Glob|WebFetch|WebSearch|Task",
                              hooks: [{type: "command", command: $pre}]}]
                            + (. | map(select((.hooks // [])[0].command != $pre))))
  | .hooks.PostToolUse |= ([{matcher: "Edit|Write|NotebookEdit|MultiEdit|Bash|Read|Grep|Glob|WebFetch|WebSearch|Task",
                              hooks: [{type: "command", command: $post}]}]
                            + (. | map(select((.hooks // [])[0].command != $post))))
  | .hooks.SessionStart |= ([{hooks: [{type: "command", command: $start}]}]
                             + (. | map(select((.hooks // [])[0].command != $start))))
  | .hooks.Stop        |= ([{hooks: [{type: "command", command: $stop}]}]
                             + (. | map(select((.hooks // [])[0].command != $stop))))
')"

if [[ $DRY_RUN -eq 1 ]]; then
  echo ""
  echo "=== Dry-run: 다음 내용으로 $SETTINGS 가 갱신됩니다 ==="
  echo "$merged" | jq '.'
  echo "=== (실제 파일은 수정 안 됨) ==="
  exit 0
fi

# 백업 후 적용
cp "$SETTINGS" "$SETTINGS.bak.$(date +%s)"
echo "$merged" > "$SETTINGS"

echo "✓ Claude Code hooks 등록 완료: $SETTINGS"
echo "  (backup: $SETTINGS.bak.*)"
