#!/bin/bash
# harness version
set -euo pipefail

HARNESS_HOME="$HOME/.harness"

echo "harness 0.0.1 ($HARNESS_HOME)"

# Standard plugins
echo ""
echo "Standard:"
[[ -f "$HARNESS_HOME/standard/AGENTS.md" ]] && echo "  ✓ AGENTS.md"
for d in "$HARNESS_HOME"/standard/*/; do
  [[ -d "$d" ]] || continue
  name="$(basename "$d")"
  case "$name" in
    adapters) ;;
    *) echo "  ✓ $name plugin" ;;
  esac
done

# Linked providers
echo ""
echo "Linked providers:"
SETTINGS="$HOME/.claude/settings.json"
if [[ -f "$SETTINGS" ]] && command -v jq >/dev/null 2>&1; then
  if jq -e '.hooks.PreToolUse[]?.hooks[]? | select(.command? // "" | contains(".harness/standard/adapters/claude"))' "$SETTINGS" >/dev/null 2>&1; then
    echo "  ✓ claude"
  fi
fi
