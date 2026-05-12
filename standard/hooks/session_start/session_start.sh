#!/bin/bash
# session_start (Claude: SessionStart) — 세션 시작 시 호출.
# 역할: 컨텍스트 초기화 + AGENTS.md 주입.
# 책임:
# 1. compose.yaml(SSOT)로부터 AGENTS.md 본문 생성 → runtime/AGENTS.resolved.md
#    (단 know-how/AGENTS.md가 있으면 그걸 그대로 사용 — 수동 override)
# 2. CLAUDE.md / 프로젝트 루트 AGENTS.md symlink 갱신
# 3. required-status.json 초기화 (compose.yaml의 required_context.paths 기반)
# 4. cognitive-guard.json 초기화

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
POLICY="$SCRIPT_DIR/lib/policy.py"

input="$(cat)"

session_id="$(echo "$input" | json_get 'session_id')"
project_root="$(echo "$input" | json_get 'project_root')"
transcript_path="$(echo "$input" | json_get 'transcript_path')"

if [[ -z "$project_root" ]]; then
  project_root="$PWD"
fi
export HARNESS_PROJECT_ROOT="$project_root"

# 안전 가드: .harness/ 없으면 즉시 통과
if [[ ! -d "$project_root/.harness" ]]; then
  json_response "allow"
fi

active_yaml="$project_root/.harness/compose.yaml"
runtime="$(runtime_dir "$project_root")"
resolved_path="$runtime/AGENTS.resolved.md"

# 1. AGENTS.md 본문 결정 (manual override > generated from compose.yaml)
manual_agents="$project_root/.harness/know-how/AGENTS.md"
if [[ -f "$manual_agents" ]] && head -1 "$manual_agents" | grep -qF "# AGENTS.md"; then
  cp "$manual_agents" "$resolved_path"
elif [[ -f "$active_yaml" ]]; then
  python3 "$POLICY" generate-agents-md "$active_yaml" > "$resolved_path"
else
  # compose.yaml 없으면 standard fallback
  cat "$HOME/.harness/standard/AGENTS.md" > "$resolved_path"
fi

# 2. CLAUDE.md symlink 갱신
claude_md="$project_root/CLAUDE.md"
if [[ ! -e "$claude_md" || -L "$claude_md" ]]; then
  ln -sfn "$resolved_path" "$claude_md"
fi

# 3. required-status.json 초기화 (compose.yaml SSOT 기반)
sf="$(status_file "$project_root" "$session_id")"
if [[ -f "$active_yaml" ]]; then
  python3 "$POLICY" init-status "$active_yaml" > "$sf"
else
  echo '{}' > "$sf"
fi

# 4. cognitive-guard 누적 상태 초기화
gf="$(guard_file "$project_root" "$session_id")"
echo '{"changed_files": [], "total_diff_lines": 0, "edit_history": []}' > "$gf"

# 4-1. 세션 메타 (transcript_path 등) 저장 — LLM-judge에서 사용
mf="$(session_dir "$project_root" "$session_id")/meta.json"
if command -v jq >/dev/null 2>&1; then
  jq -n --arg sid "$session_id" --arg tp "${transcript_path:-}" --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{session_id: $sid, transcript_path: $tp, started_at: $ts}' > "$mf"
fi

# 5. Trace 시작 이벤트
ts="$(date -u +%Y-%m-%dT%H:%M:%S.%NZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)"
trace_event=$(printf '{"ts":"%s","session_id":"%s","event_type":"session_start","resolved_md":"%s"}' \
  "$ts" "$session_id" "$resolved_path")
trace_append "$project_root" "$session_id" "$trace_event"

# 6. 사용자 인지 보조: 마지막 수정 시간
mtime="$(stat -f '%Sm' -t '%Y-%m-%d %H:%M:%S' "$resolved_path" 2>/dev/null || stat -c '%y' "$resolved_path" 2>/dev/null || echo unknown)"
reason="harness session 초기화. AGENTS.md last modified: $mtime"
json_response "allow" "$reason"
