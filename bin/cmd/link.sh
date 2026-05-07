#!/bin/bash
# harness link <provider> — provider hook 시스템에 등록.
set -euo pipefail

HARNESS_HOME="$HOME/.harness"

if [[ $# -eq 0 ]]; then
  echo "Usage: harness link <provider>" >&2
  echo "Available: claude, codex, omo" >&2
  exit 1
fi

provider="$1"
shift
register="$HARNESS_HOME/standard/adapters/$provider/register.sh"

if [[ ! -x "$register" ]]; then
  echo "Error: $provider 어댑터 미구현 (register.sh 없음)" >&2
  exit 1
fi

exec "$register" "$@"
