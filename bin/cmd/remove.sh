#!/bin/bash
# harness remove <name> — 프로젝트에서 plugin 제거.
set -euo pipefail

PROJECT_ROOT="$(pwd)"
PROJ_HARNESS="$PROJECT_ROOT/.harness"

if [[ $# -eq 0 ]]; then
  echo "Usage: harness remove <name>" >&2
  exit 1
fi

name="$1"
target="$PROJ_HARNESS/standard/$name"

if [[ ! -e "$target" && ! -L "$target" ]]; then
  echo "Error: 설치되지 않음: $target" >&2
  exit 1
fi

if [[ -L "$target" ]]; then
  rm "$target"
elif [[ -d "$target" ]]; then
  echo "주의: $target 은 forked/local. 진짜 삭제할까? [y/N]"
  read -r ans
  [[ "$ans" == "y" ]] || { echo "취소"; exit 0; }
  rm -rf "$target"
else
  rm "$target"
fi

echo "✓ Removed: $name"

# compose.yaml에서 한 줄 제거
ACTIVE="$PROJ_HARNESS/compose.yaml"
if [[ -f "$ACTIVE" ]]; then
  grep -vE "^\s*-\s+$name\s*$" "$ACTIVE" > "$ACTIVE.tmp" && mv "$ACTIVE.tmp" "$ACTIVE"
  echo "  compose.yaml에서 제거됨"
fi
