#!/bin/bash
# harness upgrade — v1 → v2 통합 마이그레이션 (standard + compose).
#
# 옵션:
#   --project <path>      대상 프로젝트 (기본: 현재 디렉토리)
#   --standard-src <path> v1 standard 명시
#   --standard-dst <path> v2 출력 명시
#   --dry-run             변경 없이 plan 만
#   --force               기존 v2 출력 덮어쓰기
set -euo pipefail

HARNESS_HOME="$HOME/.harness"

if [[ -f "$HARNESS_HOME/lib/upgrade.py" ]]; then
  LIB_ROOT="$HARNESS_HOME"
else
  LIB_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 가 필요합니다" >&2
  exit 1
fi

exec env PYTHONPATH="$LIB_ROOT" python3 -m lib.upgrade "$@"
