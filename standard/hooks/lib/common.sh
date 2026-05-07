#!/bin/bash
# Common functions for harness hooks.
# Source this from each hook script:  source "$(dirname "$0")/lib/common.sh"

set -euo pipefail

# --- 경로 헬퍼 ---

# .harness/ 위치 찾기 (project_root 기준)
harness_dir() {
  local root="${1:-${HARNESS_PROJECT_ROOT:-$PWD}}"
  echo "$root/.harness"
}

# runtime/ 폴더 (없으면 만듦)
runtime_dir() {
  local root="${1:-${HARNESS_PROJECT_ROOT:-$PWD}}"
  local d="$root/.harness/runtime"
  mkdir -p "$d"
  echo "$d"
}

# 세션별 status 폴더
session_dir() {
  local root="$1"
  local sid="$2"
  local d="$root/.harness/runtime/sessions/$sid"
  mkdir -p "$d"
  echo "$d"
}

# trace 파일 경로
trace_file() {
  local root="$1"
  local sid="$2"
  local d="$root/.harness/runtime/traces"
  mkdir -p "$d"
  echo "$d/$sid.jsonl"
}

# Required status JSON 파일 경로
status_file() {
  local root="$1"
  local sid="$2"
  echo "$(session_dir "$root" "$sid")/required-status.json"
}

# Cognitive guard 누적 상태 파일
guard_file() {
  local root="$1"
  local sid="$2"
  echo "$(session_dir "$root" "$sid")/cognitive-guard.json"
}

# Tool timing 상태 파일 (pre→post 듀레이션 측정)
timing_file() {
  local root="$1"
  local sid="$2"
  echo "$(session_dir "$root" "$sid")/timing.json"
}

# 현재 시각 ns (Linux/macOS 호환)
now_ns() {
  if date +%N 2>/dev/null | grep -qE '^[0-9]+$'; then
    date +%s%N
  else
    python3 -c 'import time; print(int(time.time()*1e9))'
  fi
}

# --- AGENTS.md 합성 (layering) ---

# layered AGENTS.md를 stdout으로 출력. know-how가 있으면 그걸, 없으면 standard.
resolve_agents_md() {
  local root="$1"
  local know_how="$root/.harness/know-how/AGENTS.md"
  local standard="$root/.harness/standard/AGENTS.md"
  if [[ -f "$know_how" ]]; then
    cat "$know_how"
  elif [[ -L "$standard" || -f "$standard" ]]; then
    cat "$standard"
  else
    # standard symlink가 없으면 글로벌 직접
    cat "$HOME/.harness/standard/AGENTS.md"
  fi
}

# AGENTS.md에서 Required Context 섹션의 path와 severity 추출
# 출력: 한 줄에 "path<TAB>severity"  (severity 미지정 시 빈 문자열)
# 라인 형식 인식:
#   - label: path
#   - label: path [hard_stop]
#   - label: path [self_correct]
#   - path
#   - path [hard_stop]
extract_required_paths() {
  local agents_md="$1"
  awk '
    /^## Required Context/ { in_section=1; next }
    in_section && /^## / { in_section=0 }
    in_section && /^- / {
      line = $0
      sub(/^- /, "", line)
      if (line ~ /^<!--/) next
      if (line ~ /^[[:space:]]*$/) next

      # severity 마킹 추출: [hard_stop] 또는 [self_correct]
      severity = ""
      if (match(line, /\[(hard_stop|self_correct)\]/)) {
        severity = substr(line, RSTART+1, RLENGTH-2)
        # 마킹 제거
        sub(/[[:space:]]*\[(hard_stop|self_correct)\][[:space:]]*$/, "", line)
      }

      # "label: path" 형식이면 path만
      if (match(line, /^[^:]+:[[:space:]]*/)) {
        line = substr(line, RLENGTH+1)
      }

      # 트림
      sub(/^[[:space:]]+/, "", line)
      sub(/[[:space:]]+$/, "", line)
      if (line == "") next

      printf "%s\t%s\n", line, severity
    }
  ' "$agents_md"
}

# --- JSON 헬퍼 ---

# stdin JSON에서 .key 추출 (jq 우선, fallback python)
json_get() {
  local key="$1"
  if command -v jq >/dev/null 2>&1; then
    jq -r ".$key // empty"
  else
    python3 -c "import json,sys; d=json.load(sys.stdin); v=d; \
$(echo "$key" | sed 's/\./].get('"'"'/g; s/^/v=v.get('"'"'/; s/$/'"'"')/' || echo "v=None")
print(v if v is not None else '')"
  fi
}

# Hook 응답 (Claude Code 프로토콜).
# - allow:        exit 0, stdout 비움
# - self_correct: exit 2, stderr에 reason (도구만 차단, 에이전트 자기 교정 가능)
# - hard_stop:    stdout에 {continue: false, stopReason}, exit 0 (전체 턴 정지)
#
# 디버깅 시 HARNESS_HOOK_DEBUG=1이면 stdout에 짧은 JSON 추가.
json_response() {
  local decision="$1"
  local reason="${2:-}"
  case "$decision" in
    allow|approve|"")
      if [[ "${HARNESS_HOOK_DEBUG:-0}" == "1" ]]; then
        printf '{"decision":"allow","reason":"%s"}\n' "${reason//\"/\\\"}"
      fi
      exit 0
      ;;
    deny|block|self_correct)
      # 도구 차단 + 에이전트는 자기 교정 시도 가능
      echo "$reason" >&2
      exit 2
      ;;
    hard_stop)
      # 전체 턴 정지. 자기 교정 X. 사용자가 다음 지시 줘야.
      if command -v jq >/dev/null 2>&1; then
        jq -n --arg r "$reason" '{continue: false, stopReason: $r}'
      else
        printf '{"continue":false,"stopReason":"%s"}\n' "${reason//\"/\\\"}"
      fi
      exit 0
      ;;
    *)
      echo "Unknown decision: $decision" >&2
      exit 1
      ;;
  esac
}

# --- Trace 기록 ---

trace_append() {
  local root="$1"
  local sid="$2"
  local event_json="$3"   # 한 줄짜리 JSON
  local f
  f="$(trace_file "$root" "$sid")"
  echo "$event_json" >> "$f"
}

# --- Decision 로그 (improve 분석용) ---
# pre_tool_use가 결정 내릴 때마다 한 줄 jsonl 기록.

decisions_file() {
  local root="$1"
  local sid="$2"
  echo "$(session_dir "$root" "$sid")/decisions.jsonl"
}

decision_log() {
  local root="$1"
  local sid="$2"
  local tool="$3"
  local decision="$4"          # allow | deny_self_correct | deny_hard_stop
  local reason_category="$5"    # required_unread | cognitive_per_call | cognitive_session | loop_detection | trigger_read | none
  local extra="${6:-}"           # 추가 메타 (예: file_path, diff_lines)
  local f
  f="$(decisions_file "$root" "$sid")"
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '{"ts":"%s","tool":"%s","decision":"%s","reason_category":"%s","extra":%s}\n' \
    "$ts" "$tool" "$decision" "$reason_category" "${extra:-null}" >> "$f"
}

# --- 에러 로그 ---

hook_log() {
  local msg="$*"
  local log_file
  log_file="$(runtime_dir "${HARNESS_PROJECT_ROOT:-$PWD}")/hook-errors.log"
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$msg" >> "$log_file"
}
