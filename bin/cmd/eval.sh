#!/bin/bash
# harness eval — case 실행·결과 보고.

set -euo pipefail

HARNESS_HOME="$HOME/.harness"
RUNNER="$HARNESS_HOME/lib/eval/runner.py"

if [[ $# -eq 0 ]]; then
  python3 "$RUNNER" --help 2>&1 | head -15
  echo ""
  echo "예:"
  echo "  harness eval list                   가용 케이스"
  echo "  harness eval run                    모든 케이스 실행"
  echo "  harness eval run required-deny      특정 케이스"
  echo "  harness eval report                 누적 결과 표"
  exit 0
fi

exec python3 "$RUNNER" "$@"
