#!/bin/bash
# harness show <name> — 특정 아티팩트의 상세 정보.
#
# 옵션:
#   --provider <id>            특정 provider 만 필터
#   --kind <mcp|skill|plugin>  특정 종류 만 필터
#   --json                     JSON 출력
set -euo pipefail

HARNESS_HOME="$HOME/.harness"
adapters_show="$HARNESS_HOME/lib/adapters/show.py"

if [[ ! -f "$adapters_show" ]]; then
  echo "Error: provider adapter 미설치 — bash install.sh 실행 필요" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 가 필요합니다" >&2
  exit 1
fi

# argparse가 usage / -h / 잘못된 인자를 자체 처리하도록 그대로 위임
export HARNESS_HOME
exec env PYTHONPATH="$HARNESS_HOME" python3 -m lib.adapters.show "$@"
