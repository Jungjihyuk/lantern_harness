#!/bin/bash
# pre_tool_use handler (v2 skeleton)
#
# Lifecycle: 변경성 도구 (Edit/Write/Bash 등) 호출 직전.
# 책임 (roles):
#   - required_check     — Required Context 미읽음 차단
#   - cognitive_guard    — 변경 규모 (per_call / per_session) 제한
#   - loop_detection     — Doom loop 감지 (같은 path 반복 수정)
#   - context_gating     — Trigger → Read 매칭 시 추가 컨텍스트 강제
#   - trace_log          — 결정 이벤트 기록
#
# stdin envelope:
#   {"hook_type":"pre_tool_use","session_id":"...","project_root":"...",
#    "tool_name":"Edit","tool_args":{...}}
#
# stdout:
#   {"decision":"allow"}                        (통과)
#   {"decision":"self_correct","reason":"..."}  (LLM 에게 안내, 재시도 유도)
#   {"decision":"hard_stop","reason":"..."}     (사용자 개입 요구)
#
# TODO: guard.policies 의 cognitive_guard / loop_detection 정책을 compose 에서 읽고,
#       lib/validator 의 결과 + status JSON 활용해 실제 검증 구현.

set -euo pipefail
input="$(cat)"

# placeholder: 일단 통과
echo '{"decision":"allow"}'
