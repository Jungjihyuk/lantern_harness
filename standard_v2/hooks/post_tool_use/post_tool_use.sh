#!/bin/bash
# post_tool_use — 도구 호출 직후.
# 책임:
# 1. Read 추적 → required-status.json 업데이트.
# 2. Edit/Write 추적 → cognitive-guard.json 누적.
# 3. Trace jsonl append.
# 4. Stuck detection 카운터.

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

ts="$(date -u +%Y-%m-%dT%H:%M:%S.%NZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)"

# --- Tool 듀레이션 계산 (pre가 기록한 start_ts와 diff) ---
duration_ms=0
tf="$(timing_file "$project_root" "$session_id")"
if [[ -f "$tf" ]] && command -v jq >/dev/null 2>&1; then
  start_ns="$(jq --arg t "$tool_name" -r '.[$t] // empty' "$tf")"
  if [[ -n "$start_ns" && "$start_ns" != "null" ]]; then
    now="$(now_ns)"
    duration_ms=$(( (now - start_ns) / 1000000 ))
    # 음수/이상치 방어
    [[ $duration_ms -lt 0 ]] && duration_ms=0
  fi
fi

# --- Trace 기록 ---
event=$(printf '{"ts":"%s","session_id":"%s","event_type":"tool_use","name":"%s","duration_ms":%s}' \
  "$ts" "$session_id" "$tool_name" "$duration_ms")
trace_append "$project_root" "$session_id" "$event"

# --- Read 추적: required-status.json 갱신 ---
if [[ "$tool_name" == "Read" ]]; then
  read_path="$(echo "$input" | json_get 'tool_args.file_path')"
  sf="$(status_file "$project_root" "$session_id")"
  if [[ -f "$sf" && -n "$read_path" ]]; then
    if command -v jq >/dev/null 2>&1; then
      tmp="$(mktemp)"
      jq --arg p "$read_path" '
        to_entries
        | map(
            .key as $k
            | if ($k == $p or ($p | endswith($k)) or ($k | endswith($p)))
              then .value.status = "read"
              else .
              end
          )
        | from_entries
      ' "$sf" > "$tmp" && mv "$tmp" "$sf"
    else
      python3 - <<PY
import json
with open("$sf") as f: d=json.load(f)
p="$read_path"
for k in list(d.keys()):
    if k == p or p.endswith(k) or k.endswith(p):
        d[k] = "read"
with open("$sf","w") as f: json.dump(d,f,indent=2)
PY
    fi
  fi
fi

# --- Edit/Write 추적: cognitive-guard.json 누적 + stuck counter ---
if [[ "$tool_name" =~ ^(Edit|Write|MultiEdit|NotebookEdit)$ ]]; then
  fp="$(echo "$input" | json_get 'tool_args.file_path')"
  gf="$(guard_file "$project_root" "$session_id")"
  # 라인 수 추정 (pre와 동일 로직)
  lines=0
  if [[ "$tool_name" == "Edit" || "$tool_name" == "MultiEdit" ]]; then
    new_str="$(echo "$input" | json_get 'tool_args.new_string')"
    old_str="$(echo "$input" | json_get 'tool_args.old_string')"
    new_l=$(printf '%s' "$new_str" | wc -l)
    old_l=$(printf '%s' "$old_str" | wc -l)
    lines=$(( new_l + old_l ))
  elif [[ "$tool_name" == "Write" ]]; then
    content="$(echo "$input" | json_get 'tool_args.content')"
    lines=$(printf '%s' "$content" | wc -l)
  fi
  if [[ -f "$gf" && -n "$fp" ]] && command -v jq >/dev/null 2>&1; then
    tmp="$(mktemp)"
    jq --arg p "$fp" --argjson n "$lines" '
      .changed_files = (.changed_files + [$p] | unique)
      | .edit_history = (.edit_history + [$p])
      | .total_diff_lines = ((.total_diff_lines // 0) + $n)
    ' "$gf" > "$tmp" && mv "$tmp" "$gf"
  fi
fi

# 항상 통과 (post는 정보성)
json_response "allow"
