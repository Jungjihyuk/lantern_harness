#!/bin/bash
# harness ralph — 무인 루프 러너 제어.
#
# 사용:
#   harness ralph start [--invoker=manual|claude]    새 run 시작
#   harness ralph status [<run-id>]                   현재 또는 특정 run 상태
#   harness ralph list                                모든 run 목록
#   harness ralph stop                                실행 중 run 정지

set -euo pipefail

HARNESS_HOME="$HOME/.harness"
PROJECT_ROOT="$(pwd)"
STATE_PY="$HARNESS_HOME/standard/ralph/lib/state.py"
RUNNER="$HARNESS_HOME/standard/ralph/runner.sh"

if [[ $# -eq 0 ]]; then
  cat <<USAGE
harness ralph — 무인 루프 러너

  harness ralph start [--invoker=manual|claude]    새 run 시작
  harness ralph status [<run-id>]                   상태
  harness ralph list                                run 목록
  harness ralph stop                                정지
USAGE
  exit 0
fi

cmd="$1"
shift

case "$cmd" in
  start)
    if [[ ! -d "$PROJECT_ROOT/.harness" ]]; then
      echo "Error: .harness/ 없음. 'harness init' 먼저." >&2
      exit 1
    fi
    exec "$RUNNER" --project-root="$PROJECT_ROOT" "$@"
    ;;
  status)
    exec python3 "$STATE_PY" status "$PROJECT_ROOT" "$@"
    ;;
  list)
    exec python3 "$STATE_PY" list "$PROJECT_ROOT"
    ;;
  stop)
    LOCK="$PROJECT_ROOT/.harness/runtime/ralph/active.lock"
    if [[ ! -f "$LOCK" ]]; then
      echo "(실행 중 ralph run 없음)"
      exit 0
    fi
    rid="$(cat "$LOCK")"
    python3 "$STATE_PY" finish "$PROJECT_ROOT" "$rid" "aborted"
    rm -f "$LOCK"
    echo "✓ ralph run $rid 정지됨"
    ;;
  *)
    echo "Unknown subcommand: $cmd" >&2
    exit 1
    ;;
esac
