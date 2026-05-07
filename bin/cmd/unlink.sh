#!/bin/bash
# harness unlink <provider> — provider hook 시스템에서 제거.
set -euo pipefail

HARNESS_HOME="$HOME/.harness"

if [[ $# -eq 0 ]]; then
  echo "Usage: harness unlink <provider>" >&2
  exit 1
fi

provider="$1"
shift
unregister="$HARNESS_HOME/standard/adapters/$provider/unregister.sh"

if [[ ! -x "$unregister" ]]; then
  echo "Error: $provider unregister.sh 없음" >&2
  exit 1
fi

exec "$unregister" "$@"
