# codex adapter

Codex CLI provider 결합 (TOML 기반). `driver.py` 구체 구현 완료.

## 책임

- **읽기**: `~/.codex/config.toml` (model / plugins / mcp_servers / marketplaces), `~/.codex/skills/<name>/SKILL.md`
- **쓰기 (disable/enable 시)**: `~/.codex/config.toml` 의 `mcp_servers` / `plugins.<id>.enabled` 토글, `SKILL.md ↔ SKILL.md.disabled` 파일명 토글
- **상태**: `${XDG_DATA_HOME}/harness/state/codex/mcp_backup.json` — disabled MCP 의 원본 설정 백업

## 특이사항

- **자체 minimal TOML 파서** — `tomli` / `tomllib` 외부 의존 없이 동작. 단, 미지원 패턴 있음: inline table, multi-line string, dotted keys (단일 라인), array of tables.
- **AGENTS.md native 인식**: Codex 가 프로젝트 루트의 `AGENTS.md` 를 system prefix 로 자동 사용하므로, `session_start` hook 이 `runtime/AGENTS.resolved.md` 를 그 위치로 symlink.

## 검증 상태

driver 구현은 완료. e2e 검증 (실제 Codex CLI 와의 hook flow / plugin lifecycle) 은 진행 중. claude adapter 와 동일한 envelope 규약을 따르므로 추가 검증 통과 시 1차 지원 승격.
