# Changelog

This project follows [Keep a Changelog](https://keepachangelog.com/) and uses
the harness's own evolution tracking philosophy.

## [Unreleased]

### Added
- 첫 공개 release 준비

## [0.1.0] — Initial public structure

### Added
- 5-Hook 시스템 (session_start / user_prompt_submit / pre_tool_use / post_tool_use / stop) + post_commit
- AGENTS.md 4 블록 자동 생성 (compose.yaml SSOT)
- Cognitive Guard + Doom Loop 감지
- Stop Validation
- Required Context per-item severity (self_correct / hard_stop)
- Trigger → Read (glob 매칭)
- Ralph 무인 루프 (단일 task / stage chain 두 모드)
- Eval 회귀 테스트 (기본 5 케이스)
- 6 viz 렌더러 + 라이브 Dashboard (SSE + 인터랙티브 편집)
- Improve (룰 기반 제안)
- LLM-as-judge (3 backend: claude_cli / codex / manual)
- Provider 어댑터 (Claude 구체 + codex placeholder)
- Evolution 자동 추적 (post-commit + CHANGELOG)
- Publish 자격 검증 (4 기준)
- 16 CLI 명령
- 문서: 입문 / 중급 / 고급 / claude hook reference / 설계 계획서 / 구현 정리
