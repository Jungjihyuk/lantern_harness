#!/bin/bash
# permission_request handler (v2 skeleton)
#
# Lifecycle: 도구가 권한이 필요한 동작 수행 직전. provider 가 사용자 승인 요청 전·후로 호출.
# 책임:
#   - permission_gate — 정책 기반으로 자동 허용/거부 또는 사용자 prompt
#   - trace_log       — 권한 요청 + 결정 기록
#
# stdin envelope:
#   {"hook_type":"permission_request","session_id":"...","tool_name":"Bash",
#    "tool_args":{"command":"rm -rf ..."},"sensitivity":"destructive"}
#
# stdout:
#   {"decision":"allow"}
#   {"decision":"ask"}   (사용자 confirm 필요)
#   {"decision":"deny","reason":"..."}
#
# TODO: compose 의 permission 정책 + provider 별 sensitivity rule 결합.

set -euo pipefail
input="$(cat)"

# placeholder: 기본 ask (사용자가 결정)
echo '{"decision":"ask"}'
