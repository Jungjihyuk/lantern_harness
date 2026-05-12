# Claude Code 어댑터

Claude Code의 hook 시스템에 우리 표준 hook을 매핑.

## 동작

`harness link claude` 실행 시 `~/.claude/settings.json`의 `hooks` 섹션에 자동 병합:

- **PreToolUse** (matcher: `Edit|Write|NotebookEdit|MultiEdit|Bash`) → `translate-pre.sh`
- **PostToolUse** (matcher: `Read|Edit|Write|MultiEdit|NotebookEdit`) → `translate-post.sh`
- **SessionStart** → `translate-start.sh`

기존 settings.json은 `.bak.<timestamp>`로 백업. 다른 hook entry는 그대로 보존.

## AGENTS.md 주입

`before_agent` hook이 `<project>/.harness/runtime/AGENTS.resolved.md`를 작성하고, 프로젝트 루트의 `CLAUDE.md`로 symlink. Claude의 native auto-load 메커니즘 활용.

## 입출력 변환

translate-*.sh가 jq로 envelope 변환:
- claude `tool_input` ↔ 표준 `tool_args`
- claude `cwd` ↔ 표준 `project_root`
- claude `hook_event_name` ↔ 표준 `hook_type`

claude의 응답 포맷(`{decision, reason}`)이 표준 envelope와 동일하므로 응답은 그대로 전달.

## 제거

`harness unlink claude` → `unregister.sh` 호출 → 우리 hook entry 제거.
