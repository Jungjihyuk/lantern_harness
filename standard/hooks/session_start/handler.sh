#!/bin/bash
# session_start handler (v2 skeleton)
#
# Lifecycle: provider 가 세션 시작 시 envelope JSON 을 stdin 으로 전달.
# 책임:
#   - prefix_injection — compose.v2.yaml 의 cognition.instructions 와 rules 를 모아 AGENTS.md(또는 CLAUDE.md) 생성
#   - status_init      — runtime 상태 파일 초기화 (required context 읽음 추적용)
#   - trace_log        — 세션 시작 이벤트 기록
#
# stdin envelope (예):
#   {"hook_type":"session_start","session_id":"...","project_root":"...","transcript_path":"..."}
#
# stdout 응답:
#   {"decision":"allow"}   (또는 메타 정보)
#
# TODO: lib/resolver + lib/compose 활용해 v2 compose 읽어 AGENTS.md 생성하는 로직 추가.

set -euo pipefail
input="$(cat)"

# placeholder: 일단 통과
echo '{"decision":"allow"}'
