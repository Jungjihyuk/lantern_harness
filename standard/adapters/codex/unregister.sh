#!/bin/bash
# Codex 의 프로젝트 또는 글로벌 hooks.json 에서 harness entry 제거.

set -euo pipefail

PROJECT_ROOT="$(pwd)"
HARNESS_HOME="$HOME/.harness"
ADAPTER_DIR="$HARNESS_HOME/standard/adapters/codex"

SCOPE="project"
for arg in "$@"; do
  case "$arg" in
    --global)  SCOPE="global" ;;
    --project) SCOPE="project" ;;
  esac
done

if [[ "$SCOPE" == "global" ]]; then
  HOOKS_FILE="$HOME/.codex/hooks.json"
else
  HOOKS_FILE="$PROJECT_ROOT/.codex/hooks.json"
fi

if [[ ! -f "$HOOKS_FILE" ]]; then
  echo "hooks.json 파일 없음: $HOOKS_FILE"
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq required" >&2
  exit 1
fi

PRE="$ADAPTER_DIR/translate-pre.sh"
POST="$ADAPTER_DIR/translate-post.sh"
START="$ADAPTER_DIR/translate-start.sh"
STOP="$ADAPTER_DIR/translate-stop.sh"
PROMPT="$ADAPTER_DIR/translate-prompt.sh"
PERM="$ADAPTER_DIR/translate-permission.sh"

cp "$HOOKS_FILE" "$HOOKS_FILE.bak.$(date +%s)"

tmp="$(mktemp)"
jq --arg pre "$PRE" \
   --arg post "$POST" \
   --arg start "$START" \
   --arg stop "$STOP" \
   --arg prompt "$PROMPT" \
   --arg perm "$PERM" '
  if .hooks then
    .hooks.SessionStart = ((.hooks.SessionStart // []) | map(select((.hooks // [])[0].command != $start)))
    | .hooks.UserPromptSubmit = ((.hooks.UserPromptSubmit // []) | map(select((.hooks // [])[0].command != $prompt)))
    | .hooks.PreToolUse = ((.hooks.PreToolUse // []) | map(select((.hooks // [])[0].command != $pre)))
    | .hooks.PermissionRequest = ((.hooks.PermissionRequest // []) | map(select((.hooks // [])[0].command != $perm)))
    | .hooks.PostToolUse = ((.hooks.PostToolUse // []) | map(select((.hooks // [])[0].command != $post)))
    | .hooks.Stop = ((.hooks.Stop // []) | map(select((.hooks // [])[0].command != $stop)))
  else . end
' "$HOOKS_FILE" > "$tmp" && mv "$tmp" "$HOOKS_FILE"

echo "✓ Codex hooks 제거 완료: $HOOKS_FILE"
echo "  (backup: $HOOKS_FILE.bak.*)"
