#!/bin/bash
# post_tool_batch handler (v2 skeleton)
#
# Lifecycle: LLM 이 한 차례 도구들을 묶어 호출한 batch 가 끝난 시점.
# 책임:
#   - metric_collect — batch 단위 토큰·시간·도구 수 누적
#   - state_diagnose — batch 안 변화로 인한 상태 변동 진단 (예: "큰 변경 후 상태 점검")
#
# stdin envelope:
#   {"hook_type":"post_tool_batch","session_id":"...","batch_id":"...",
#    "tools": [{"name":"Edit","duration_ms":...}, ...],
#    "elapsed_ms": 1234}
#
# stdout: 메타 정보 (응답 미사용).

set -euo pipefail
input="$(cat)"

# placeholder: 단순 ack
echo '{}'
