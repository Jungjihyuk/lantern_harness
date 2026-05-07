#!/bin/bash
# harness improve — 사용 패턴 기반 compose.yaml 조정 제안.
set -euo pipefail
exec python3 "$HOME/.harness/lib/improve/main.py" "$@"
