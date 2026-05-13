#!/bin/bash
# harness ctx <subcommand> — 컨텍스트 inspection.
#
# Subcommands:
#   budget   compose 의 cognition entries 별 토큰 예산 + 비율

set -euo pipefail

HARNESS_HOME="$HOME/.harness"

# dev repo fallback — lib 가 ~/.harness 에 없으면 repo root 의 lib 사용
if [[ -d "$HARNESS_HOME/lib/ctx" ]]; then
  LIB_ROOT="$HARNESS_HOME"
else
  LIB_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
fi

SUB="${1:-}"
[[ $# -gt 0 ]] && shift

case "$SUB" in
  budget)
    export HARNESS_HOME
    exec env PYTHONPATH="$LIB_ROOT" python3 -m lib.ctx.budget "$@"
    ;;
  ""|-h|--help)
    cat <<USAGE
Usage: harness ctx <subcommand>

Subcommands:
  budget    compose 의 cognition entries 별 토큰 예산 + 비율
USAGE
    ;;
  *)
    echo "Error: unknown ctx subcommand '$SUB'" >&2
    echo "Try: harness ctx --help" >&2
    exit 1
    ;;
esac
