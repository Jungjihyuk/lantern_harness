#!/bin/bash
# post_tool_use_failure handler (v2 skeleton)
#
# Lifecycle: 도구 호출이 에러로 끝난 직후.
# 책임:
#   - trace_log    — 실패 이벤트 기록 (tool, args, error)
#   - eval_verdict — 실패 패턴 분류 (transient retry-able vs systemic vs user-action-required)
#
# stdin envelope:
#   {"hook_type":"post_tool_use_failure","session_id":"...",
#    "tool_name":"Bash","tool_args":{...},"error":{"code":1,"stderr":"..."}}
#
# stdout:
#   {"verdict":"retry"}      (LLM 에게 재시도 권장)
#   {"verdict":"systemic"}   (구조적 문제 — 다른 접근 권유)
#   {"verdict":"user_block"} (사용자 개입 필요)
#
# TODO: 실패 분류 휴리스틱 + observe.evals 의 결과 인지.

set -euo pipefail
input="$(cat)"

# placeholder: retry 권장
echo '{"verdict":"retry"}'
