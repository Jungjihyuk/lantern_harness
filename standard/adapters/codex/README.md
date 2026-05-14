# codex adapter

Codex CLI provider 결합. driver (Python) + 6 hook translate scripts + register/unregister 셸 entry 까지 구체 구현 완료.

## 구성

| 파일 | 책임 |
|---|---|
| `driver.py` | `CodexDriver(ProviderDriver)` — `~/.codex/config.toml` / skills / MCP 관리. `harness list` / `show` / `enable` / `disable` 의 `--provider codex` 분기에 사용. |
| `register.sh` | `<repo>/.codex/hooks.json` (또는 `--global` 시 `~/.codex/hooks.json`) 에 6 이벤트 hook entry 등록. `[features] codex_hooks = true` 와 project trust 사전 검사 안내 포함. |
| `unregister.sh` | hooks.json 에서 우리 entry 제거 (다른 entry 는 보존). |
| `translate-start.sh` | `SessionStart` → `session_start` handler + `runtime/AGENTS.resolved.md` → `<project>/AGENTS.md` symlink 생성. |
| `translate-prompt.sh` | `UserPromptSubmit` → `user_prompt_submit` handler. |
| `translate-pre.sh` | `PreToolUse` → `pre_tool_use` handler. block 시 `permissionDecision: "deny"` 응답. |
| `translate-permission.sh` | `PermissionRequest` → `permission_request` handler. `decision.behavior` allow/deny 응답. |
| `translate-post.sh` | `PostToolUse` → `post_tool_use` handler. |
| `translate-stop.sh` | `Stop` → `stop` handler. `self_correct` → 재개, `hard_stop` → 완전 중단. |

## 등록 흐름

```bash
harness link codex            # <repo>/.codex/hooks.json 에 등록 (기본)
harness link codex --global   # ~/.codex/hooks.json 에 등록
harness link codex --dry-run  # 미리보기
```

`register.sh` 가 다음을 사전 검사:
1. `~/.codex/config.toml` 에 `[features] codex_hooks = true` 존재 여부
2. (project scope) 현재 프로젝트가 `[projects."<cwd>"] trust_level = "trusted"` 인지

둘 중 누락이어도 등록은 진행 — 동작 안 한다는 경고만 출력 (사용자 config 침범 안 함).

## 자체 minimal TOML 파서

driver 는 `tomli` / `tomllib` 외부 의존 없이 동작. 단, 미지원 패턴 있음:
- inline table
- multi-line string
- dotted keys (단일 라인)
- array of tables

Codex 의 `config.toml` 중 우리가 다루는 단순 구조 (섹션 헤더, 단순 key-value, 주석) 만 커버.

## AGENTS.md native 인식

Codex 는 프로젝트 루트의 `AGENTS.md` 를 system prefix 로 자동 사용. `translate-start.sh` 가 매 세션마다 `<project>/.harness/runtime/AGENTS.resolved.md` 를 `<project>/AGENTS.md` 로 symlink (사용자가 작성한 일반 파일 AGENTS.md 가 있으면 건드리지 않음).

## Claude 와의 차이 (요약)

자세한 비교는 [`docs/codex-hook-reference.md`](../../../docs/codex-hook-reference.md) 의 §7 참조.

- 등록 위치: `hooks.json` 별도 파일 (vs `settings.local.json` 통합)
- 이벤트 1 종 추가: `PermissionRequest`
- `Stop` 의 `decision: "block"` 의미 반대 (재개) — `translate-stop.sh` 가 처리
- `PreToolUse` 가 `Bash` / `apply_patch` / MCP 만 가로챔 (claude 는 모든 도구)
- 같은 이벤트 hook 들이 **동시 launch** (순서 의존 정책 X)

## 검증 상태

shell entry 구현 완료. e2e 검증 (실제 Codex CLI 세션에서 hook flow 가 trace 까지 닿는지) 는 진행 중. 검증 통과 시 README / CHANGELOG 의 codex 표현을 "2차 지원" 으로 정식 갱신 예정.
