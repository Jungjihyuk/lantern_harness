# codex adapter (placeholder)

Codex 사용 시점에 구체화 예정.

## 채움 가이드

같은 패턴(`register.sh` + `unregister.sh` + `translate-*.sh`)으로 작성.

Codex는 AGENTS.md를 native 인식하므로 `session_start` hook이 `runtime/AGENTS.resolved.md`를 프로젝트 루트 `AGENTS.md`로 symlink.

Codex의 PreToolUse/PostToolUse 같은 hook 메커니즘은 codex CLI 문서 참조해 매핑.
