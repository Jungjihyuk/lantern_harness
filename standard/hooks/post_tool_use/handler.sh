#!/bin/bash
# post_tool_use handler (v2 skeleton)
#
# Lifecycle: 도구 호출 성공 후.
# 책임:
#   - trace_log      — 도구·결과·duration 기록
#   - metric_collect — 토큰·라인·시간 누적
#   - status_track   — Read 도구 호출 → required_context status JSON 갱신
#
# stdin envelope:
#   {"hook_type":"post_tool_use","session_id":"...","project_root":"...",
#    "tool_name":"Read","tool_args":{...},"duration_ms":42,"result":{...}}
#
# stdout: 응답 미사용 (post hook 은 결정 X). 그래도 envelope 일관성 위해 빈 응답.

set -euo pipefail
input="$(cat)"

# placeholder: 통과
echo '{}'
