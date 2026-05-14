#!/bin/bash
# harness enable <name> — 특정 아티팩트를 enabled 상태로 전환.
#
# 옵션:
#   --provider <id>            특정 provider 만 필터
#   --kind <mcp|skill|plugin>  특정 종류 만 필터
#   --dry-run                  실제 변경 없이 예정만 출력
set -euo pipefail

HARNESS_HOME="$HOME/.harness"
entry="$HARNESS_HOME/lib/adapters/enable.py"

if [[ ! -f "$entry" ]]; then
  echo "Error: provider adapter 미설치 — bash install.sh 실행 필요" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 가 필요합니다" >&2
  exit 1
fi

export HARNESS_HOME
exec env PYTHONPATH="$HARNESS_HOME" python3 -m lib.adapters.enable "$@"
