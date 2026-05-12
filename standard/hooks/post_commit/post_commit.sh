#!/bin/bash
# harness evolution post-commit hook 진입점.
# .git/hooks/post-commit이 이걸 호출 → evolution.py가 CHANGELOG 갱신.

set -euo pipefail

PROJECT_ROOT="${1:-$(pwd)}"
EVOL="$HOME/.harness/standard/hooks/lib/evolution.py"

# 안전 가드
[[ -d "$PROJECT_ROOT/.harness" ]] || exit 0
[[ -f "$EVOL" ]] || exit 0

python3 "$EVOL" "$PROJECT_ROOT" || true
