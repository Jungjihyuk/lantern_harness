#!/bin/bash
# stop handler (v2 skeleton)
#
# Lifecycle: LLM 응답 종료 직전. checks 통과해야 응답 종료 허용.
# 책임:
#   - stop_validation — compose 의 guard.policies.stop_validation.checks 실행
#   - trace_log       — 종료 이벤트 기록
#
# stdin envelope:
#   {"hook_type":"stop","session_id":"...","project_root":"..."}
#
# stdout:
#   {"decision":"allow"}   (종료 허용)
#   {"decision":"block","reason":"..."}  (작업 미완료 → LLM 재작업 유도)
#
# TODO: guard.policies.stop_validation 의 checks 리스트를 compose 에서 읽어 실행.

set -euo pipefail
input="$(cat)"

# placeholder: 통과
echo '{"decision":"allow"}'
