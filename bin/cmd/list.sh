#!/bin/bash
# harness list — harness 내부 아티팩트 + provider별 설치 아티팩트 통합 뷰.
#
# 옵션 (전달 시 provider 섹션만 출력):
#   --provider <id>            특정 provider만
#   --kind <mcp|skill|plugin>  특정 종류만
#   --json                     JSON 출력
set -euo pipefail

HARNESS_HOME="$HOME/.harness"
PROJECT_ROOT="$(pwd)"
PROJ_HARNESS="$PROJECT_ROOT/.harness"

# 플래그가 있으면 harness 내부 섹션은 생략하고 provider 섹션만 출력
show_harness_section=1
for arg in "$@"; do
  case "$arg" in
    --provider|--kind|--json|--provider=*|--kind=*)
      show_harness_section=0
      ;;
  esac
done

if [[ $show_harness_section -eq 1 ]]; then
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
fi

# === Provider 통합 아티팩트 (Claude Code, ...) ===
adapters_list="$HARNESS_HOME/standard/adapters/list.py"
if [[ -f "$adapters_list" ]] && command -v python3 >/dev/null 2>&1; then
  if [[ $show_harness_section -eq 1 ]]; then
    echo ""
    echo "PROVIDERS:"
  fi
  python3 "$adapters_list" "$@"
fi
