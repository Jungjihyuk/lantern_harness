# Changelog

This project follows [Keep a Changelog](https://keepachangelog.com/) and uses
the harness's own evolution tracking philosophy.

## [Unreleased]

_(없음)_

## [0.1.0] — Initial public structure

### Added

- **아키텍처**: 5 책임 도메인 (`cognition` / `state` / `action` / `guard` / `observe`) × 7 메커니즘 폴더 (`instructions` / `hooks` / `tools` / `adapters` / `workflows` / `traces` / `evals`) 직교 분류 — 효과(도메인)와 구현(메커니즘) 분리, N:N 매핑
- **artifact 단위**: `<mechanism>/<id>/manifest.yaml + entry` 패턴, 폴더 한 단위로 추가/이동/삭제
- **compose.yaml schema**: `cognition.prefix` + `cognition.context` 3-단 (`required` / `triggered` / `suggested`) + `state.workflows[ralph]` + `guard.policies.cognitive_guard` — AGENTS.md 자동 생성 (compose SSOT)
- **5-Hook 시스템**: `session_start` / `user_prompt_submit` / `pre_tool_use` / `post_tool_use` / `stop` + `post_commit`
- **가드레일**: Cognitive Guard · Doom Loop 감지 · Stop Validation · Required Context per-item severity (`self_correct` / `hard_stop`) · Trigger → Read (glob 매칭)
- **Ralph 무인 루프**: `state.workflows[ralph]` 명세 기반 task → verify 반복
- **Eval 회귀 테스트**: manifest 기반 runner + 기본 회귀 케이스 (loop_detection / cognitive_guard / required_context / stop_validation / edit_track 등)
- **6 viz 렌더러**: `workflow` / `subagents` / `bottleneck` / `eval` / `improve` / `prompts`
- **`harness viz dashboard`**: read-only SSE 라이브 대시보드
- **`harness dashboard`**: n8n 스타일 인터랙티브 web 편집기 — compose entry CRUD · 노드 drag&drop · artifact 본문 인라인 편집
- **Improve**: 사용 패턴 분석 + 룰 기반 제안
- **LLM-as-judge**: 3 backend (`claude_cli` / `codex` / `manual`)
- **Provider 어댑터**: Claude 1차 지원 (driver + hook 등록) · Codex 2차 지원 — `driver.py` 구체 구현 (`~/.codex/config.toml` 관리 / skills / MCP / 자체 TOML 파서)
- **Standard 자산**: instructions (`agents_md` / `agents_md_karpathy` / `templates`) · hooks 7 종 (`session_start` / `pre_tool_use` / `post_tool_use` / `post_tool_use_failure` / `post_tool_batch` / `stop` / `permission_request`) · workflows (`ralph`) · evals (회귀 케이스 + manifest 패턴)
- **CLI 20 명령**: `init` · `link` · `unlink` · `reload` · `list` · `show` · `enable` · `disable` · `validate` · `ctx` · `publish` · `scaffold` · `dashboard` · `viz` · `eval` · `improve` · `judge` · `ralph` (start / status / list / stop) · `doctor` · `version`
- **Evolution**: post-commit + CHANGELOG 자동 추적
- **Publish**: know-how → standard 승격 (자격 검증)
- **문서**: `01-입문` / `02-중급` / `03-고급` / `architecture` / `system-essence` / `provider-adapter` / `claude-hook-reference` / `dashboard-manual-test`
