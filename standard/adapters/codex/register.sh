#!/bin/bash
# Codex 의 프로젝트 또는 글로벌 hooks.json 에 harness 의 표준 hook entry 자동 등록.
# 사용자의 ~/.codex/config.toml 은 직접 수정하지 않음 (feature flag 누락 시 안내만).
#
# 옵션:
#   --dry-run    실제 파일 수정 없이 미리보기만 출력
#   --global     ~/.codex/hooks.json 에 글로벌 등록 — 명시적 옵트인
#   --project    <repo>/.codex/hooks.json 에 등록 (기본)
#
# 사전 전제:
#   1. ~/.codex/config.toml 에 [features] codex_hooks = true
#   2. 프로젝트 등록 시 그 프로젝트가 trust_level = "trusted"
#   둘 다 누락이어도 등록은 진행 — 동작 안 할 거라는 경고만 출력.

set -euo pipefail

PROJECT_ROOT="$(pwd)"
HARNESS_HOME="$HOME/.harness"
ADAPTER_DIR="$HARNESS_HOME/standard/adapters/codex"

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

# 대상 hooks.json 결정
if [[ "$SCOPE" == "global" ]]; then
  HOOKS_FILE="$HOME/.codex/hooks.json"
  echo "⚠ 글로벌 등록 모드 — 모든 codex 세션·모든 프로젝트에 영향"
else
  HOOKS_FILE="$PROJECT_ROOT/.codex/hooks.json"
  echo "프로젝트 로컬 등록 — $PROJECT_ROOT 만 영향"
  if [[ ! -d "$PROJECT_ROOT/.harness" ]]; then
    echo "⚠ 경고: $PROJECT_ROOT/.harness/ 없음. 'harness init' 먼저 실행 권장."
  fi
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq required" >&2
  exit 1
fi

# ── 사전 검사: codex_hooks feature flag ────────────────────────────────
CODEX_CONFIG="$HOME/.codex/config.toml"
if [[ -f "$CODEX_CONFIG" ]]; then
  if ! grep -qE '^\s*codex_hooks\s*=\s*true' "$CODEX_CONFIG"; then
    echo ""
    echo "⚠ ~/.codex/config.toml 에 [features] codex_hooks = true 가 없음."
    echo "   hook 시스템이 disable 된 상태라 등록해도 동작 안 함."
    echo "   다음을 추가하세요:"
    echo "       [features]"
    echo "       codex_hooks = true"
  fi
else
  echo ""
  echo "⚠ ~/.codex/config.toml 미존재. codex 가 설치돼 있는지 확인하세요."
fi

# ── 사전 검사: 프로젝트 trust (project scope 만) ──────────────────────────
if [[ "$SCOPE" == "project" && -f "$CODEX_CONFIG" ]]; then
  # [projects."<path>"] trust_level = "trusted" 패턴 검사
  # 단순 grep — config.toml 의 multi-line 구조라 완전 정확하진 않지만 흔한 케이스 커버
  if ! grep -qF "[projects.\"$PROJECT_ROOT\"]" "$CODEX_CONFIG"; then
    echo ""
    echo "⚠ ~/.codex/config.toml 에 이 프로젝트가 trusted 로 등록 안 됨."
    echo "   codex 는 untrusted 프로젝트의 .codex/ 를 무시하므로 hook 이 동작 안 함."
    echo "   다음을 추가하세요:"
    echo "       [projects.\"$PROJECT_ROOT\"]"
    echo "       trust_level = \"trusted\""
  fi
fi

# ── 디렉토리·파일 준비 ─────────────────────────────────────────────────
if [[ $DRY_RUN -eq 0 ]]; then
  mkdir -p "$(dirname "$HOOKS_FILE")"
  if [[ ! -f "$HOOKS_FILE" ]]; then
    echo '{}' > "$HOOKS_FILE"
  fi
fi

current="$(cat "$HOOKS_FILE" 2>/dev/null || echo '{}')"

# ── harness entry 병합 ─────────────────────────────────────────────────
# - 우리 command path 와 일치하는 기존 entry 는 제거 후 우리 entry 추가 (중복 방지)
# - 다른 사람/도구의 entry 는 그대로 보존
PRE="$ADAPTER_DIR/translate-pre.sh"
POST="$ADAPTER_DIR/translate-post.sh"
START="$ADAPTER_DIR/translate-start.sh"
STOP="$ADAPTER_DIR/translate-stop.sh"
PROMPT="$ADAPTER_DIR/translate-prompt.sh"
PERM="$ADAPTER_DIR/translate-permission.sh"

# tool 매처: Bash + apply_patch (Edit/Write alias 포함) + MCP tools
TOOL_MATCHER="Bash|apply_patch|Edit|Write|mcp__.*"

merged="$(echo "$current" | jq \
  --arg pre "$PRE" \
  --arg post "$POST" \
  --arg start "$START" \
  --arg stop "$STOP" \
  --arg prompt "$PROMPT" \
  --arg perm "$PERM" \
  --arg tool_matcher "$TOOL_MATCHER" '
  .hooks //= {}
  | .hooks.SessionStart //= []
  | .hooks.UserPromptSubmit //= []
  | .hooks.PreToolUse //= []
  | .hooks.PermissionRequest //= []
  | .hooks.PostToolUse //= []
  | .hooks.Stop //= []
  | .hooks.SessionStart |= ([{
        matcher: "startup|resume",
        hooks: [{type: "command", command: $start, statusMessage: "harness session_start"}]
      }] + (. | map(select((.hooks // [])[0].command != $start))))
  | .hooks.UserPromptSubmit |= ([{
        hooks: [{type: "command", command: $prompt, statusMessage: "harness user_prompt_submit"}]
      }] + (. | map(select((.hooks // [])[0].command != $prompt))))
  | .hooks.PreToolUse |= ([{
        matcher: $tool_matcher,
        hooks: [{type: "command", command: $pre, statusMessage: "harness pre_tool_use"}]
      }] + (. | map(select((.hooks // [])[0].command != $pre))))
  | .hooks.PermissionRequest |= ([{
        matcher: $tool_matcher,
        hooks: [{type: "command", command: $perm, statusMessage: "harness permission_request"}]
      }] + (. | map(select((.hooks // [])[0].command != $perm))))
  | .hooks.PostToolUse |= ([{
        matcher: $tool_matcher,
        hooks: [{type: "command", command: $post, statusMessage: "harness post_tool_use"}]
      }] + (. | map(select((.hooks // [])[0].command != $post))))
  | .hooks.Stop |= ([{
        hooks: [{type: "command", command: $stop, statusMessage: "harness stop"}]
      }] + (. | map(select((.hooks // [])[0].command != $stop))))
')"

if [[ $DRY_RUN -eq 1 ]]; then
  echo ""
  echo "=== Dry-run: 다음 내용으로 $HOOKS_FILE 가 갱신됩니다 ==="
  echo "$merged" | jq '.'
  echo "=== (실제 파일은 수정 안 됨) ==="
  exit 0
fi

# 백업 후 적용
cp "$HOOKS_FILE" "$HOOKS_FILE.bak.$(date +%s)"
echo "$merged" > "$HOOKS_FILE"

echo ""
echo "✓ Codex hooks 등록 완료: $HOOKS_FILE"
echo "  (backup: $HOOKS_FILE.bak.*)"
echo ""
echo "  등록된 이벤트: SessionStart / UserPromptSubmit / PreToolUse / PermissionRequest / PostToolUse / Stop"
echo ""
echo "  ⚠ 참고: 이 등록은 ~/.codex/config.toml 의 [features] codex_hooks = true 가 활성일 때만 동작합니다."
