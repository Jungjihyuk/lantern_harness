#!/bin/bash
# harness list — 가용/설치 plugin 목록.
set -euo pipefail

HARNESS_HOME="$HOME/.harness"
PROJECT_ROOT="$(pwd)"
PROJ_HARNESS="$PROJECT_ROOT/.harness"

echo "GLOBAL ($HARNESS_HOME/standard):"

# Standard md
for f in "$HARNESS_HOME"/standard/*.md; do
  [[ -f "$f" ]] || continue
  name="$(basename "$f")"
  [[ "$name" == "README.md" ]] && continue
  installed="?"
  if [[ -e "$PROJ_HARNESS/standard/$name" ]]; then
    installed="installed"
  else
    installed="available"
  fi
  printf "  %s  [%s]\n" "$name" "$installed"
done

# Plugin folders
for d in "$HARNESS_HOME"/standard/*/; do
  [[ -d "$d" ]] || continue
  name="$(basename "$d")"
  [[ "$name" == "adapters" ]] && continue
  installed="available"
  if [[ -e "$PROJ_HARNESS/standard/$name" ]]; then
    installed="installed"
  fi
  printf "  %s  [%s]\n" "$name" "$installed"
done

if [[ -d "$PROJ_HARNESS" ]]; then
  echo ""
  echo "PROJECT ($PROJ_HARNESS/standard):"
  for entry in "$PROJ_HARNESS"/standard/*; do
    [[ -e "$entry" ]] || continue
    name="$(basename "$entry")"
    target=""
    if [[ -L "$entry" ]]; then
      target="$(readlink "$entry")"
      printf "  %s → %s\n" "$name" "$target"
    else
      printf "  %s [forked/local]\n" "$name"
    fi
  done

  echo ""
  echo "Know-how ($PROJ_HARNESS/know-how):"
  for entry in "$PROJ_HARNESS"/know-how/*; do
    [[ -e "$entry" ]] || continue
    printf "  %s\n" "$(basename "$entry")"
  done
fi
