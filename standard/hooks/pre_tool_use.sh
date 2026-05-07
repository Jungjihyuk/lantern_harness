#!/bin/bash
# pre_tool_use — 도구 호출 직전.
# 책임:
# 1. 변경 도구(Edit/Write/NotebookEdit/변경성 Bash)에 대해 Required Context 읽음 검증.
# 2. Cognitive guard 메트릭 검사 (per-call).
# 3. Bypass marker (`@harness allow-large`) 처리.
#
# stdin envelope:
# {
#   "hook_type": "pre_tool_use",
#   "session_id": "...",
#   "project_root": "...",
#   "tool_name": "Edit",
#   "tool_args": {...}
# }

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

input="$(cat)"

session_id="$(echo "$input" | json_get 'session_id')"
project_root="$(echo "$input" | json_get 'project_root')"
tool_name="$(echo "$input" | json_get 'tool_name')"

if [[ -z "$project_root" ]]; then
  project_root="$PWD"
fi
export HARNESS_PROJECT_ROOT="$project_root"

# 안전 가드: .harness/ 없으면 즉시 통과 (harness 미적용 프로젝트 보호)
if [[ ! -d "$project_root/.harness" ]]; then
  json_response "allow"
  exit 0
fi

# 시간 측정용 시작 시각 기록 (모든 도구에 대해)
tf="$(timing_file "$project_root" "$session_id")"
ts_ns="$(now_ns)"
if command -v jq >/dev/null 2>&1; then
  if [[ -f "$tf" ]]; then
    jq --arg t "$tool_name" --argjson n "$ts_ns" '. + {($t): $n}' "$tf" > "$tf.tmp" 2>/dev/null && mv "$tf.tmp" "$tf"
  else
    jq -n --arg t "$tool_name" --argjson n "$ts_ns" '{($t): $n}' > "$tf"
  fi
fi

# bypass marker 사전 검사 (이후 모든 분기에서 사용)
bypass_used_in_session=0

# 변경 도구가 아니면 즉시 통과 (Read/Grep/Glob/WebFetch 등)
case "$tool_name" in
  Edit|Write|NotebookEdit|MultiEdit)
    is_modifying=1
    ;;
  Bash)
    # Bash는 인자에 따라 다름. tool_args.command 검사
    cmd="$(echo "$input" | json_get 'tool_args.command')"
    # 변경성 패턴 (단순 휴리스틱)
    if echo "$cmd" | grep -qE '(\brm\b|>>?\s|\bmv\b|\bcp\b|\bdd\b|git\s+(commit|push|reset|checkout|branch|merge|rebase)|npm\s+install|pip\s+install|cargo\s+(install|build))'; then
      is_modifying=1
    else
      is_modifying=0
    fi
    ;;
  *)
    is_modifying=0
    ;;
esac

if [[ $is_modifying -eq 0 ]]; then
  json_response "allow"
  exit 0
fi

# --- Trigger → Read 매칭 ---
# Edit/Write의 file_path가 compose.yaml의 trigger_read 패턴에 매칭되면 require 문서를
# Required와 동일하게 강제. 매칭 시 동적으로 status JSON에 추가 (이미 있으면 skip).
file_path="$(echo "$input" | json_get 'tool_args.file_path')"
sf="$(status_file "$project_root" "$session_id")"
active_yaml="$project_root/.harness/compose.yaml"
POLICY="$SCRIPT_DIR/lib/policy.py"

if [[ -n "$file_path" && -f "$active_yaml" && -f "$POLICY" ]] && command -v jq >/dev/null 2>&1; then
  trig_json="$(python3 "$POLICY" match-triggers "$active_yaml" "$file_path" 2>/dev/null || echo '[]')"
  if [[ "$trig_json" != "[]" && -n "$trig_json" ]]; then
    # status JSON에 동적으로 추가
    [[ -f "$sf" ]] || echo '{}' > "$sf"
    while IFS= read -r entry; do
      [[ -z "$entry" ]] && continue
      req="$(echo "$entry" | jq -r '.require')"
      on_deny="$(echo "$entry" | jq -r '.on_deny')"
      # 이미 있으면 status·on_deny 보존, 없으면 unread로 추가
      tmp="$(mktemp)"
      jq --arg p "$req" --arg od "$on_deny" '
        if (.[$p] // null) == null
        then . + {($p): {status: "unread", on_deny: $od}}
        else .
        end
      ' "$sf" > "$tmp" && mv "$tmp" "$sf"
    done < <(echo "$trig_json" | jq -c '.[]')
  fi
fi

# --- Required Context 읽음 검증 ---
if [[ -f "$sf" ]] && command -v jq >/dev/null 2>&1; then
  # 미읽음 path들과 그들의 on_deny severity 추출
  unread_data="$(jq -r '
    to_entries
    | map(select(.value.status == "unread"))
    | map({key: .key, on_deny: (.value.on_deny // "self_correct")})
  ' "$sf")"

  unread_count="$(echo "$unread_data" | jq 'length')"

  if [[ "$unread_count" != "0" ]]; then
    # 어떤 항목이라도 hard_stop이면 hard_stop, 아니면 self_correct
    has_hard="$(echo "$unread_data" | jq '[.[] | select(.on_deny == "hard_stop")] | length')"
    unread_paths="$(echo "$unread_data" | jq -r '[.[] | .key] | join(", ")')"

    if [[ "$has_hard" != "0" ]]; then
      hard_paths="$(echo "$unread_data" | jq -r '[.[] | select(.on_deny == "hard_stop") | .key] | join(", ")')"
      decision_log "$project_root" "$session_id" "$tool_name" "deny_hard_stop" "required_unread" "{\"unread\":\"$hard_paths\"}"
      json_response "hard_stop" "[hard_stop] Required Context 미읽음: $hard_paths. 진행 중지 — 사용자가 직접 Read 후 재시도 요청."
    else
      decision_log "$project_root" "$session_id" "$tool_name" "deny_self_correct" "required_unread" "{\"unread\":\"$unread_paths\"}"
      json_response "self_correct" "Required Context 미읽음: $unread_paths. 먼저 Read 도구로 읽으세요."
    fi
  fi
fi

# --- 공통 설정 (loop_detection · cognitive_guard 둘 다 사용) ---
bypass_marker="@harness allow-large"
if [[ -f "$active_yaml" ]]; then
  v="$(awk '/^cognitive_guard:/{f=1; next} f && /^[a-zA-Z]/{f=0} f && /^  bypass_marker:/{$1=""; print; exit}' "$active_yaml" | sed 's/^[[:space:]]*//; s/^"//; s/"$//')"
  [[ -n "$v" ]] && bypass_marker="$v"
fi

# --- Loop Detection (Doom loop 방어) ---
# edit_history의 마지막 N개가 모두 같은 file_path면 의미 없는 반복으로 간주.
if [[ "$tool_name" =~ ^(Edit|Write|MultiEdit|NotebookEdit)$ && -n "$file_path" ]]; then
  loop_threshold=3
  loop_on=self_correct
  loop_enabled=true
  if [[ -f "$active_yaml" ]]; then
    v="$(awk '/^loop_detection:/{f=1; next} f && /^[a-zA-Z]/{f=0} f && /^  consecutive_same_path:/{print $2; exit}' "$active_yaml")"
    [[ -n "$v" ]] && loop_threshold="$v"
    v="$(awk '/^loop_detection:/{f=1; next} f && /^[a-zA-Z]/{f=0} f && /^  on_loop:/{print $2; exit}' "$active_yaml")"
    [[ -n "$v" ]] && loop_on="$v"
    v="$(awk '/^loop_detection:/{f=1; next} f && /^[a-zA-Z]/{f=0} f && /^  enabled:/{print $2; exit}' "$active_yaml")"
    [[ -n "$v" ]] && loop_enabled="$v"
  fi
  if [[ "$loop_enabled" == "true" ]]; then
    gf_loop="$(guard_file "$project_root" "$session_id")"
    if [[ -f "$gf_loop" ]] && command -v jq >/dev/null 2>&1; then
      # 마지막 (threshold-1)개가 모두 같은 file_path && 새 호출도 같은 path면 N개 연속
      need=$(( loop_threshold - 1 ))
      same="$(jq -r --argjson n "$need" --arg p "$file_path" '
        (.edit_history // []) as $h
        | if ($h | length) >= $n
          then ($h | reverse | .[0:$n] | unique | length == 1) and ($h[-1] == $p)
          else false
          end
      ' "$gf_loop" 2>/dev/null)"
      if [[ "$same" == "true" ]]; then
        reason="Doom loop 감지: ${file_path}를 ${loop_threshold}번 연속 수정. 다른 접근 시도하세요. (의도면 '${bypass_marker}' 추가)"
        # bypass marker 검사
        if echo "$input" | grep -qF "$bypass_marker"; then
          bypass_used_in_session=1
          decision_log "$project_root" "$session_id" "$tool_name" "allow" "loop_detection" "{\"bypass\":true,\"file\":\"$file_path\"}"
        else
          decision_log "$project_root" "$session_id" "$tool_name" "deny_$loop_on" "loop_detection" "{\"file\":\"$file_path\",\"threshold\":$loop_threshold}"
          json_response "$loop_on" "$reason"
        fi
      fi
    fi
  fi
fi

# --- Cognitive guard per-call 검사 ---
# compose.yaml 읽어 임계값 가져오기 (단순 grep/awk; yq 있으면 더 정밀)
active_yaml="$project_root/.harness/compose.yaml"
max_diff_lines=200
max_new_files=3
on_breach="ask_human"
max_session_files=10
max_session_diff=1000
if [[ -f "$active_yaml" ]]; then
  v="$(awk '/^  per_call:/{f=1; next} f && /^  [a-zA-Z]/{f=0} f && /^    max_diff_lines:/{print $2; exit}' "$active_yaml")"
  [[ -n "$v" ]] && max_diff_lines="$v"
  v="$(awk '/^  per_call:/{f=1; next} f && /^  [a-zA-Z]/{f=0} f && /^    max_new_files:/{print $2; exit}' "$active_yaml")"
  [[ -n "$v" ]] && max_new_files="$v"
  v="$(awk '/^  per_session:/{f=1; next} f && /^  [a-zA-Z]/{f=0} f && /^    max_changed_files:/{print $2; exit}' "$active_yaml")"
  [[ -n "$v" ]] && max_session_files="$v"
  v="$(awk '/^  per_session:/{f=1; next} f && /^  [a-zA-Z]/{f=0} f && /^    max_diff_lines:/{print $2; exit}' "$active_yaml")"
  [[ -n "$v" ]] && max_session_diff="$v"
  v="$(awk '/^cognitive_guard:/{f=1; next} f && /^[a-zA-Z]/{f=0} f && /^  on_breach:/{print $2; exit}' "$active_yaml")"
  [[ -n "$v" ]] && on_breach="$v"
fi

# Edit/Write 인자에서 변경 라인 수 추정
diff_lines=0
new_file=0
if [[ "$tool_name" == "Edit" || "$tool_name" == "MultiEdit" ]]; then
  new_str="$(echo "$input" | json_get 'tool_args.new_string')"
  old_str="$(echo "$input" | json_get 'tool_args.old_string')"
  new_lines=$(printf '%s' "$new_str" | wc -l)
  old_lines=$(printf '%s' "$old_str" | wc -l)
  diff_lines=$(( new_lines + old_lines ))
elif [[ "$tool_name" == "Write" ]]; then
  content="$(echo "$input" | json_get 'tool_args.content')"
  diff_lines=$(printf '%s' "$content" | wc -l)
  fp="$(echo "$input" | json_get 'tool_args.file_path')"
  [[ -e "$fp" ]] || new_file=1
fi

# Bypass marker 검사 (prompt에 마커가 있는 경우 — 어댑터가 metadata로 전달)
bypass=0
if echo "$input" | grep -qF "$bypass_marker"; then
  bypass=1
fi

if [[ $bypass -eq 0 ]]; then
  # per-call: 라인 수
  if [[ $diff_lines -gt $max_diff_lines ]]; then
    reason="큰 변경 감지 (per-call): ${diff_lines} 라인 (한도 ${max_diff_lines}). 의도된 것이면 prompt에 '${bypass_marker}' 추가."
    if [[ "$on_breach" == "warn" ]]; then
      hook_log "WARN cognitive guard: $reason"
    else
      decision_log "$project_root" "$session_id" "$tool_name" "deny_self_correct" "cognitive_per_call" "{\"diff_lines\":$diff_lines,\"max\":$max_diff_lines}"
      json_response "self_correct" "$reason"
    fi
  fi

  # per-session: 누적 변경 파일 수, 누적 라인 수
  gf="$(guard_file "$project_root" "$session_id")"
  if [[ -f "$gf" ]] && command -v jq >/dev/null 2>&1; then
    sess_files=$(jq -r '(.changed_files // []) | length' "$gf" 2>/dev/null || echo 0)
    sess_diff=$(jq -r '(.total_diff_lines // 0)' "$gf" 2>/dev/null || echo 0)
    new_files_count=$sess_files
    if [[ -n "$file_path" ]] && ! jq -e --arg p "$file_path" '.changed_files | index($p)' "$gf" >/dev/null 2>&1; then
      new_files_count=$(( sess_files + 1 ))
    fi
    if [[ $new_files_count -gt $max_session_files ]]; then
      reason="세션 누적 변경 파일 ${new_files_count}개 (한도 ${max_session_files}). 의도면 '${bypass_marker}' 추가."
      if [[ "$on_breach" != "warn" ]]; then
        decision_log "$project_root" "$session_id" "$tool_name" "deny_self_correct" "cognitive_session_files" "{\"files\":$new_files_count,\"max\":$max_session_files}"
        json_response "self_correct" "$reason"
      fi
    fi
    projected_diff=$(( sess_diff + diff_lines ))
    if [[ $projected_diff -gt $max_session_diff ]]; then
      reason="세션 누적 변경 라인 ${projected_diff} (한도 ${max_session_diff}). 의도면 '${bypass_marker}' 추가."
      if [[ "$on_breach" != "warn" ]]; then
        decision_log "$project_root" "$session_id" "$tool_name" "deny_self_correct" "cognitive_session_lines" "{\"lines\":$projected_diff,\"max\":$max_session_diff}"
        json_response "self_correct" "$reason"
      fi
    fi
  fi
else
  # bypass 사용 — 통과지만 흔적 남김
  decision_log "$project_root" "$session_id" "$tool_name" "allow" "cognitive_per_call" "{\"bypass\":true,\"diff_lines\":$diff_lines}"
fi

# 모든 검사 통과
decision_log "$project_root" "$session_id" "$tool_name" "allow" "none" "null"
json_response "allow"
