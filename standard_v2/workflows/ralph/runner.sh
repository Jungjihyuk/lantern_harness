#!/bin/bash
# Ralph runner v1 — invoker로 agent 호출 + verify + stuck detection.
#
# 사용:
#   ralph/runner.sh <project_root> [--invoker=<name>]
# 또는 (권장):
#   harness ralph start [--invoker=<name>]
#
# compose.yaml의 ralph 섹션 읽어 동작:
#   ralph.task           — single mode 작업 명세 path
#   ralph.stages         — chain mode 시퀀스 (미구현 v1)
#   ralph.max_iterations — 최대 반복 (default 20)
#   ralph.stuck_threshold
#   ralph.on_stuck

set -uo pipefail

PROJECT_ROOT="$(pwd)"
INVOKER="manual"   # default

# 옵션 파싱
for arg in "$@"; do
  case "$arg" in
    --invoker=*) INVOKER="${arg#--invoker=}" ;;
    --project-root=*) PROJECT_ROOT="${arg#--project-root=}" ;;
  esac
done

PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd)"
HARNESS_HOME="$HOME/.harness"
RALPH_DIR="$HARNESS_HOME/standard/ralph"
ACTIVE="$PROJECT_ROOT/.harness/compose.yaml"
STATE="$RALPH_DIR/lib/state.py"

# compose.yaml 검증
if [[ ! -f "$ACTIVE" ]]; then
  echo "Error: $ACTIVE 없음. 'harness init' 먼저." >&2
  exit 1
fi

# 이미 다른 ralph 실행 중인가?
if [[ -f "$PROJECT_ROOT/.harness/runtime/ralph/active.lock" ]]; then
  active_rid="$(cat "$PROJECT_ROOT/.harness/runtime/ralph/active.lock" 2>/dev/null)"
  echo "Error: 다른 ralph run 진행 중: $active_rid" >&2
  echo "정지하려면: harness ralph stop" >&2
  exit 1
fi

# compose.yaml에서 ralph 설정 추출
get_ralph() {
  python3 -c "
import yaml
cfg = yaml.safe_load(open('$ACTIVE')) or {}
r = cfg.get('ralph') or {}
v = r.get('$1', '$2')
print(v if v is not None else '')
"
}

TASK="$(get_ralph task '')"
STAGES="$(get_ralph stages '')"
MAX_ITER="$(get_ralph max_iterations 20)"
STUCK_THRESHOLD="$(get_ralph stuck_threshold 3)"
ON_STUCK="$(get_ralph on_stuck ask_human)"

if [[ -n "$STAGES" ]]; then
  echo "Note: stage chain 모드는 v1에 미구현. single task 모드만 지원." >&2
fi

if [[ -z "$TASK" ]]; then
  echo "Error: compose.yaml의 ralph.task 없음" >&2
  exit 1
fi

TASK_FILE="$PROJECT_ROOT/${TASK#./}"
if [[ ! -f "$TASK_FILE" ]]; then
  echo "Error: task 파일 없음: $TASK_FILE" >&2
  exit 1
fi

# Invoker 선택
INVOKER_SH="$RALPH_DIR/invokers/$INVOKER.sh"
if [[ ! -x "$INVOKER_SH" ]]; then
  # know-how에서 찾기
  INVOKER_SH="$PROJECT_ROOT/.harness/know-how/ralph/invokers/$INVOKER.sh"
  if [[ ! -x "$INVOKER_SH" ]]; then
    echo "Error: invoker 없음: $INVOKER" >&2
    exit 1
  fi
fi

# Run 시작
RUN_ID="$(python3 "$STATE" create "$PROJECT_ROOT" "$TASK_FILE")"
RUN_DIR="$PROJECT_ROOT/.harness/runtime/ralph/runs/$RUN_ID"
echo "🚀 ralph run started: $RUN_ID"
echo "   task: $TASK_FILE"
echo "   invoker: $INVOKER"
echo "   max_iterations: $MAX_ITER"
echo ""

# Cleanup on exit
on_exit() {
  rc=$?
  if [[ $rc -ne 0 && $rc -ne 99 ]]; then
    python3 "$STATE" finish "$PROJECT_ROOT" "$RUN_ID" "aborted" >/dev/null 2>&1 || true
    echo ""
    echo "⚠ ralph run aborted ($RUN_ID)"
  fi
}
trap on_exit EXIT INT

# Verify 실행 (간단 모드)
run_verify() {
  local v_out="$1"
  if grep -q "^  verify:" "$ACTIVE"; then
    # 계층 모드 (v1: command만 지원)
    python3 -c "
import yaml, subprocess, sys
cfg = yaml.safe_load(open('$ACTIVE'))
checks = (cfg.get('ralph') or {}).get('verify') or []
for c in checks:
    if not isinstance(c, dict): continue
    if 'command' in c:
        r = subprocess.run(c['command'], shell=True, cwd='$PROJECT_ROOT', capture_output=True, text=True)
        sys.stdout.write(r.stdout); sys.stderr.write(r.stderr)
        if r.returncode != 0: sys.exit(r.returncode)
    elif 'script' in c:
        s = '$PROJECT_ROOT/' + c['script'].lstrip('./')
        r = subprocess.run(['bash', s], cwd='$PROJECT_ROOT', capture_output=True, text=True)
        sys.stdout.write(r.stdout); sys.stderr.write(r.stderr)
        if r.returncode != 0: sys.exit(r.returncode)
" > "$v_out" 2>&1
  else
    # 간단 모드
    local v="$PROJECT_ROOT/.harness/know-how/ralph/verify.sh"
    if [[ -x "$v" ]]; then
      bash "$v" > "$v_out" 2>&1
    else
      bash "$RALPH_DIR/verify.sh" > "$v_out" 2>&1
    fi
  fi
  return $?
}

# Loop
TASK_TEXT="$(cat "$TASK_FILE")"
PROMPT_TEXT="$TASK_TEXT"
START_TS=$(date +%s)

for ((i=1; i<=MAX_ITER; i++)); do
  echo ""
  echo "═══ Iteration $i / $MAX_ITER ═══"

  PROMPT_FILE="$RUN_DIR/prompts/$i.txt"
  RESPONSE_FILE="$RUN_DIR/responses/$i.txt"
  VERIFY_FILE="$RUN_DIR/verify-results/$i.txt"
  echo "$PROMPT_TEXT" > "$PROMPT_FILE"

  # Invoke
  ITER_START=$(date +%s)
  if ! "$INVOKER_SH" "$PROMPT_FILE" "$RESPONSE_FILE"; then
    rc=$?
    if [[ $rc -eq 99 ]]; then
      echo "⚠ invoker 미지원, manual로 fallback"
      INVOKER_SH="$RALPH_DIR/invokers/manual.sh"
      "$INVOKER_SH" "$PROMPT_FILE" "$RESPONSE_FILE" || { echo "abort"; exit 1; }
    elif [[ $rc -eq 1 ]]; then
      echo "사용자 abort"
      python3 "$STATE" finish "$PROJECT_ROOT" "$RUN_ID" "aborted" >/dev/null 2>&1
      exit 1
    fi
  fi

  # Verify
  echo "  verify 실행 중..."
  if run_verify "$VERIFY_FILE"; then
    verdict="pass"
  else
    verdict="fail"
  fi
  ITER_DUR=$(( $(date +%s) - ITER_START ))

  # 상태 기록
  python3 "$STATE" append "$PROJECT_ROOT" "$RUN_ID" "{\"n\":$i,\"verify\":\"$verdict\",\"duration_s\":$ITER_DUR}"

  if [[ "$verdict" == "pass" ]]; then
    echo "✓ verify 통과 — $i 회 만에 완료"
    python3 "$STATE" finish "$PROJECT_ROOT" "$RUN_ID" "passed" >/dev/null 2>&1
    TOTAL_DUR=$(( $(date +%s) - START_TS ))
    echo "총 소요: ${TOTAL_DUR}s"
    exit 0
  fi

  echo "✗ verify 실패. 다음 iteration 준비..."
  V_OUT="$(cat "$VERIFY_FILE" | head -20)"
  PROMPT_TEXT="이전 iteration의 verify가 실패했습니다.

== 원래 task ==
$TASK_TEXT

== 이전 verify 출력 ==
$V_OUT

이 verify를 통과하도록 수정해주세요. 응답이 끝나면 응답 파일에 저장하세요."
done

echo "✗ max_iterations ($MAX_ITER) 도달, verify 미통과"
python3 "$STATE" finish "$PROJECT_ROOT" "$RUN_ID" "failed" >/dev/null 2>&1
exit 1
