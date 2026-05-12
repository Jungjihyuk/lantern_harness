#!/bin/bash
# stop (Claude: Stop) — 응답 완료 직전 발동.
# 역할: 응답 완료 전 작업 검증.
# 책임:
# 1. AGENTS.md 4 블록 구조 위반 검증 (기본)
# 2. compose.yaml의 stop_validation.checks 실행 (옵션)
# 3. 실패 시 on_fail 정책에 따라 warn 또는 block (block은 exit 2로 차단)

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

input="$(cat)"

session_id="$(echo "$input" | json_get 'session_id')"
project_root="$(echo "$input" | json_get 'project_root')"
[[ -z "$project_root" ]] && project_root="$PWD"
export HARNESS_PROJECT_ROOT="$project_root"

# 안전 가드
if [[ ! -d "$project_root/.harness" ]]; then
  json_response "allow"
fi

active_yaml="$project_root/.harness/compose.yaml"

# --- 1. AGENTS.md 구조 검증 (가벼움, 항상 실행) ---
warnings=""
resolved="$(runtime_dir "$project_root")/AGENTS.resolved.md"
if [[ -f "$resolved" ]]; then
  for header in "## Required Context" "## On-Demand Context" "## Trigger → Read" "## Hard Rules"; do
    if ! grep -qF "$header" "$resolved"; then
      warnings+="AGENTS.md 누락 블록: $header. "
    fi
  done
fi

# --- 2. compose.yaml의 stop_validation.checks 실행 ---
checks_failed=()
checks_output=""

if [[ -f "$active_yaml" ]] && command -v python3 >/dev/null 2>&1; then
  enabled="$(python3 -c "
import yaml
try:
    cfg = yaml.safe_load(open('$active_yaml'))
    pc = cfg.get('stop_validation') or {}
    print('true' if pc.get('enabled') else 'false')
except Exception:
    print('false')
")"

  if [[ "$enabled" == "true" ]]; then
    on_fail="$(python3 -c "
import yaml
cfg = yaml.safe_load(open('$active_yaml'))
print((cfg.get('stop_validation') or {}).get('on_fail', 'warn'))
")"

    # check 실패가 정상 흐름이라 set -e 끔 (common.sh가 켰을 수 있음)
    set +e

    # checks 리스트 추출 (각 라인에 type: payload)
    while IFS=$'\t' read -r ctype cval; do
      [[ -z "$ctype" ]] && continue
      label="$ctype: $cval"
      if [[ "$ctype" == "command" ]]; then
        out="$(cd "$project_root" && bash -c "$cval" 2>&1)"
        rc=$?
      elif [[ "$ctype" == "script" ]]; then
        # script path는 project_root 기준
        spath="$project_root/${cval#./}"
        if [[ -x "$spath" ]]; then
          out="$(bash "$spath" 2>&1)"
          rc=$?
        else
          out="script not found or not executable: $spath"
          rc=1
        fi
      else
        out="unknown check type: $ctype"
        rc=1
      fi
      if [[ $rc -ne 0 ]]; then
        checks_failed+=("$label")
        checks_output+=$'\n--- '"$label"' ---\n'"${out:0:500}"
      fi
    done < <(python3 -c "
import yaml
cfg = yaml.safe_load(open('$active_yaml'))
checks = (cfg.get('stop_validation') or {}).get('checks') or []
for c in checks:
    if isinstance(c, dict):
        if 'command' in c:
            print(f'command\t{c[\"command\"]}')
        elif 'script' in c:
            print(f'script\t{c[\"script\"]}')
")

    if [[ ${#checks_failed[@]} -gt 0 ]]; then
      summary="stop_validation 검증 실패 (${#checks_failed[@]}개): ${checks_failed[*]}"
      hook_log "STOP_VALIDATION FAIL: $summary"
      if [[ "$on_fail" == "block" ]]; then
        # 차단 — exit 2 + stderr (claude는 계속 작업)
        echo "$summary" >&2
        echo "$checks_output" >&2
        exit 2
      else
        # warn — 통과하되 메시지 추가
        warnings+="$summary. "
      fi
    fi
  fi
fi

# --- Trace 기록 ---
ts="$(date -u +%Y-%m-%dT%H:%M:%S.%NZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)"
fail_count=${#checks_failed[@]}
event=$(printf '{"ts":"%s","session_id":"%s","event_type":"stop","checks_failed":%d}' \
  "$ts" "$session_id" "$fail_count")
trace_append "$project_root" "$session_id" "$event"

# --- 응답 ---
if [[ -n "$warnings" ]]; then
  hook_log "STOP_VALIDATION WARN: $warnings"
  json_response "allow" "$warnings"
else
  json_response "allow"
fi
