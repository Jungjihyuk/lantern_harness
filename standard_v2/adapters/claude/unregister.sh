#!/bin/bash
# Claude Code의 프로젝트 또는 글로벌 settings에서 우리 hook entry 제거.

set -euo pipefail

PROJECT_ROOT="$(pwd)"
HARNESS_HOME="$HOME/.harness"
ADAPTER_DIR="$HARNESS_HOME/standard/adapters/claude"

SCOPE="project"
for arg in "$@"; do
  case "$arg" in
    --global)  SCOPE="global" ;;
    --project) SCOPE="project" ;;
  esac
done

if [[ "$SCOPE" == "global" ]]; then
  SETTINGS="$HOME/.claude/settings.json"
else
  SETTINGS="$PROJECT_ROOT/.claude/settings.local.json"
fi

if [[ ! -f "$SETTINGS" ]]; then
  echo "settings 파일 없음: $SETTINGS"
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq required" >&2
  exit 1
fi

cp "$SETTINGS" "$SETTINGS.bak.$(date +%s)"

tmp="$(mktemp)"
jq --arg pre "$ADAPTER_DIR/translate-pre.sh" \
   --arg post "$ADAPTER_DIR/translate-post.sh" \
   --arg start "$ADAPTER_DIR/translate-start.sh" \
   --arg stop "$ADAPTER_DIR/translate-stop.sh" \
   --arg prompt "$ADAPTER_DIR/translate-prompt.sh" '
  if .hooks then
    .hooks.PreToolUse  = ((.hooks.PreToolUse // []) | map(select((.hooks // [])[0].command != $pre)))
    | .hooks.PostToolUse = ((.hooks.PostToolUse // []) | map(select((.hooks // [])[0].command != $post)))
    | .hooks.SessionStart = ((.hooks.SessionStart // []) | map(select((.hooks // [])[0].command != $start)))
    | .hooks.Stop = ((.hooks.Stop // []) | map(select((.hooks // [])[0].command != $stop)))
    | .hooks.UserPromptSubmit = ((.hooks.UserPromptSubmit // []) | map(select((.hooks // [])[0].command != $prompt)))
  else . end
' "$SETTINGS" > "$tmp" && mv "$tmp" "$SETTINGS"

echo "✓ Claude Code hooks 제거 완료: $SETTINGS"
