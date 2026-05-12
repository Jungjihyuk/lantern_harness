#!/bin/bash
# harness validate — compose.yaml v2 + manifests + roles.yaml 통합 검증.
#
# 옵션:
#   --compose <path>    compose.yaml 위치 (기본: .harness/compose.yaml)
#   --standard <path>   standard 루트 (기본: ~/.harness/standard)
#   --know-how <path>   know-how 루트 (기본: .harness/know-how)
set -euo pipefail

HARNESS_HOME="$HOME/.harness"

# v2 모듈(validate_cli.py)이 ~/.harness/lib 에 있으면 설치 환경, 아니면 repo root (개발).
# 단순히 ~/.harness/lib 디렉토리 존재로 판단하지 않음 — v1 의 lib 와 혼동 회피.
if [[ -f "$HARNESS_HOME/lib/validate_cli.py" ]]; then
  LIB_ROOT="$HARNESS_HOME"
else
  LIB_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 가 필요합니다" >&2
  exit 1
fi

exec env PYTHONPATH="$LIB_ROOT" python3 -m lib.validate_cli "$@"
