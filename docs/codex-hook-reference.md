# Codex Hook 시스템 레퍼런스

[입문 §10](01-입문.md#10-hook-시스템) 의 hook 시스템이 참조하는 외부 레퍼런스. Codex CLI 가 hook 시스템에서 **무엇을 기대하는지**, harness 의 표준 envelope 과 어떻게 매핑되는지의 detail.

> 공식 문서: [codex hooks](https://developers.openai.com/codex/hooks) · [config reference](https://developers.openai.com/codex/config-reference)

> ⚠ Codex 의 hooks 는 비교적 최근에 stable. 기능을 쓰려면 `[features] hooks = true` (또는 옛 이름 `codex_hooks = true`) 활성화 필요 (자세히는 §3).

## 목차

1. [#1. Hook 이벤트 종류](#1-hook-이벤트-종류)
2. [#2. 등록 방법 — hooks.json 과 인라인 config.toml](#2-등록-방법--hooksjson-과-인라인-configtoml)
3. [#3. 활성화 — feature flag + project trust](#3-활성화--feature-flag--project-trust)
4. [#4. Envelope — stdin·stdout 규약](#4-envelope--stdinstdout-규약)
5. [#5. Exit Code 프로토콜](#5-exit-code-프로토콜)
6. [#6. JSON 출력 — 이벤트별 응답 형식](#6-json-출력--이벤트별-응답-형식)
7. [#7. Claude 와의 비교](#7-claude-와의-비교)
8. [#8. Harness adapter 매핑 가이드](#8-harness-adapter-매핑-가이드)

---

## 1. Hook 이벤트 종류

Codex 가 발생시키는 hook 이벤트 (총 6 종):

| 이벤트 | 발동 시점 | matcher 적용 대상 |
|---|---|---|
| `SessionStart` | 새 세션 시작 시 | `source` (`startup` / `resume` / `clear`) |
| `UserPromptSubmit` | 사용자 prompt 제출 직후 (모델 호출 직전) | 미지원 — 모든 호출 |
| `PreToolUse` | 도구 호출 *직전* (`Bash` / `apply_patch` / MCP) | `tool_name` 또는 alias (`Edit` / `Write`) |
| `PermissionRequest` | Codex 가 승인 요청을 하려는 시점 | `tool_name` |
| `PostToolUse` | 도구 실행 *직후* (실패 포함) | `tool_name` |
| `Stop` | 응답 종료 시점 (재개 가능) | 미지원 — 모든 호출 |

각 이벤트에 등록된 hook 은 stdin 으로 envelope JSON 을 받고, 종료 코드·stdout 으로 결과를 알림.

> **제약**: `PreToolUse` / `PostToolUse` 는 `Bash` / `apply_patch` / MCP tool 만 가로챔. `WebSearch` / `unified_exec` 의 일부 호출은 가로채지 못함 — 가드레일이지만 **완전한 enforcement boundary 는 아님**.

> **동시 실행**: 같은 이벤트에 매칭된 여러 hook 은 **동시에** 실행됨. 한 hook 이 다른 hook 의 실행을 막을 수 없음.

---

## 2. 등록 방법 — `hooks.json` 과 인라인 `config.toml`

Codex 는 두 가지 형식 중 하나로 hook 을 등록.

### 2.1 `hooks.json` 형식

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.codex/hooks/session_start.py",
            "statusMessage": "Loading session notes"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/pre_tool_use.sh",
            "statusMessage": "Checking Bash command"
          }
        ]
      }
    ]
  }
}
```

### 2.2 인라인 `[hooks]` (config.toml)

```toml
[features]
codex_hooks = true

[[hooks.PreToolUse]]
matcher = "^Bash$"

[[hooks.PreToolUse.hooks]]
type = "command"
command = "python3 /path/to/pre_tool_use_policy.py"
timeout = 30
statusMessage = "Checking managed Bash command"
```

### 2.3 탐색 위치 (우선순위 아님 — 모두 merge)

```
~/.codex/hooks.json
~/.codex/config.toml          ([hooks] 섹션)
<repo>/.codex/hooks.json
<repo>/.codex/config.toml     ([hooks] 섹션)
```

여러 layer 의 hook 이 모두 **누적**되어 동작. 같은 layer 안에서 `hooks.json` + 인라인 `[hooks]` 둘 다 있으면 merge 하면서 경고 발생 — **layer 당 한 형식**으로 통일 권장.

---

## 3. 활성화 — feature flag + project trust

### 3.1 Feature flag

Hook 시스템 전체가 feature flag 뒤에 있음:

```toml
# ~/.codex/config.toml
[features]
hooks = true
```

이게 없으면 hook 자체가 로드되지 않음. 옛 이름 `codex_hooks = true` 도 호환 (codex 가 이름을 마이그레이션 중). 새 환경에선 `hooks` 권장.

### 3.2 Project trust

프로젝트 로컬 hook (`<repo>/.codex/hooks.json` 또는 `<repo>/.codex/config.toml` 의 `[hooks]`) 은 해당 프로젝트가 *trusted* 일 때만 로드됨:

```toml
[projects."/path/to/my/project"]
trust_level = "trusted"
```

untrusted 프로젝트에서는 사용자·시스템 layer 의 hook 만 동작 — 프로젝트의 `.codex/` 전체가 무시됨 (hooks · rules · 로컬 config 포함).

---

## 4. Envelope — stdin·stdout 규약

### 4.1 Common input (모든 이벤트 공통, stdin)

```json
{
  "session_id": "abc123",
  "transcript_path": "/path/to/transcript.jsonl",
  "cwd": "/path/to/project",
  "hook_event_name": "PreToolUse",
  "model": "gpt-5.5"
}
```

| 필드 | 의미 |
|---|---|
| `session_id` | 세션·스레드 id |
| `transcript_path` | 세션 transcript 경로 (없으면 null) |
| `cwd` | 세션의 작업 디렉토리 |
| `hook_event_name` | 현재 이벤트 이름 |
| `model` | 활성 모델 슬러그 |

turn-scoped 이벤트는 추가로 `turn_id` 필드를 받음.

### 4.2 이벤트별 추가 필드

| 이벤트 | 추가 필드 |
|---|---|
| `SessionStart` | `source` (`"startup"` / `"resume"` / `"clear"`) |
| `UserPromptSubmit` | `turn_id`, `prompt` |
| `PreToolUse` | `turn_id`, `tool_name`, `tool_use_id`, `tool_input` |
| `PermissionRequest` | `turn_id`, `tool_name`, `tool_input` (+ `tool_input.description` 있을 수 있음) |
| `PostToolUse` | `turn_id`, `tool_name`, `tool_use_id`, `tool_input`, `tool_response` |
| `Stop` | `turn_id`, `stop_hook_active`, `last_assistant_message` |

### 4.3 Common output (일부 이벤트만)

`SessionStart` / `UserPromptSubmit` / `Stop` 은 다음 공통 JSON 필드를 지원:

```json
{
  "continue": true,
  "stopReason": "optional",
  "systemMessage": "optional",
  "suppressOutput": false
}
```

- `continue: false` → 해당 hook 실행을 중단 처리
- `stopReason` → 중단 사유 기록
- `systemMessage` → UI/이벤트 스트림에 경고로 표시
- `suppressOutput` → 파싱은 되지만 미구현

`PreToolUse` / `PermissionRequest` 는 `systemMessage` 만 지원. `PostToolUse` 는 `systemMessage` + `continue: false` + `stopReason` 지원.

---

## 5. Exit Code 프로토콜

| Exit Code | 의미 |
|---|---|
| `0` | 성공. stdout JSON 이 있으면 그 내용 적용. plain text 처리는 이벤트별로 다름. |
| `2` | **차단 시그널**. stderr 의 텍스트가 차단/재개 사유로 사용됨. |
| 기타 | 일반 실패. Codex 가 hook 실패를 보고하지만 동작은 계속. |

`exit 2 + stderr` 는 JSON 응답 대신 사용할 수 있는 **간이 차단 방법**. JSON 응답이 더 풍부하지만 stdout 파싱이 까다로울 때 exit 2 가 단순.

---

## 6. JSON 출력 — 이벤트별 응답 형식

### 6.1 SessionStart — 컨텍스트 주입

```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "Load the workspace conventions before editing."
  }
}
```

`additionalContext` 는 *추가 developer context* 로 모델에 주입됨. plain text 를 stdout 에 그대로 써도 같은 효과.

### 6.2 UserPromptSubmit — 컨텍스트 추가 / 차단

추가 context:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Ask for a clearer reproduction before editing files."
  }
}
```

차단:
```json
{
  "decision": "block",
  "reason": "Ask for confirmation before doing that."
}
```

또는 `exit 2` + stderr 에 사유.

### 6.3 PreToolUse — 도구 호출 차단

권장 형식 (신):
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Destructive command blocked by hook."
  }
}
```

레거시 형식 (구):
```json
{
  "decision": "block",
  "reason": "Destructive command blocked by hook."
}
```

또는 `exit 2` + stderr.

> ⚠ `permissionDecision: "allow"` / `"ask"`, `updatedInput`, `additionalContext`, `continue: false` 등은 파싱은 되지만 **PreToolUse 에선 미구현**. 현재는 `deny` 만 의미 있음.

### 6.4 PermissionRequest — 승인 요청에 응답

승인:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow"
    }
  }
}
```

거부:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "deny",
      "message": "Blocked by repository policy."
    }
  }
}
```

여러 hook 응답 중 **`deny` 가 우선**. 아무 hook 도 결정 안 하면 Codex 의 기본 승인 흐름 진행.

### 6.5 PostToolUse — 사후 차단·메시지

```json
{
  "decision": "block",
  "reason": "Output review caught a policy violation."
}
```

도구는 이미 실행됐으므로 *후처리만* 가능 — side effect 를 되돌릴 수는 없음.

### 6.6 Stop — 응답 종료 시점 (재개 트리거)

```json
{
  "decision": "block",
  "reason": "Run one more pass over the failing tests."
}
```

`Stop` 의 `decision: "block"` 은 *턴 거부*가 아니라 **계속 진행**: `reason` 이 새 user prompt 로 들어가서 한 턴 더 진행됨.

확실히 중단하려면:
```json
{ "continue": false, "stopReason": "Truly done." }
```

여러 매칭 hook 중 하나라도 `continue: false` 면 그 결정이 우선.

---

## 7. Claude 와의 비교

| 차원 | Claude Code | Codex CLI |
|---|---|---|
| **활성화** | 기본 활성 | `[features] hooks = true` (또는 옛 `codex_hooks`) 필요 |
| **등록 위치** | `~/.claude/settings.json` 또는 `<project>/.claude/settings.local.json` | `hooks.json` 또는 `[hooks]` 인라인 (4 location merge) |
| **layer 합성** | 글로벌 / 프로젝트 *중 한쪽* | 모든 layer **누적** |
| **프로젝트 trust** | 별도 trust 모델 없음 (settings.local.json 은 그냥 로컬) | `trust_level = "trusted"` 인 프로젝트만 `.codex/` 로드 |
| **이벤트 종류** | 5 (`SessionStart` / `UserPromptSubmit` / `PreToolUse` / `PostToolUse` / `Stop`) | 6 — 위 5 종 + `PermissionRequest` |
| **stdin 공통 필드** | `session_id` / `transcript_path` / `cwd` / `permission_mode` / `hook_event_name` | `session_id` / `transcript_path` / `cwd` / `hook_event_name` / `model` |
| **응답 형식** | `{decision, reason}` 또는 exit code | `hookSpecificOutput` (신) / `{decision, reason}` (구) / exit 2 |
| **exit 2** | block 시그널 (stderr 메시지) | 동일 — block/continue 시그널 (stderr 메시지) |
| **PreToolUse 차단 범위** | 모든 tool | `Bash` / `apply_patch` / MCP 만 (`WebSearch` 등 미가로챔) |
| **동시 실행 시 충돌** | 순차 실행 가능 | 매칭 hook **동시 launch** — 한쪽이 다른 쪽을 막을 수 없음 |
| **Stop 의 `block`** | 응답 종료 차단 | 응답 종료 차단이 아니라 **자동 재개 (continuation prompt)** |

**구조적으로 비슷한 부분:**
- 이벤트 이름이 거의 동일 (`SessionStart` / `UserPromptSubmit` / `PreToolUse` / `PostToolUse` / `Stop`)
- stdin JSON / stdout JSON / exit code 의 3 채널
- exit 2 + stderr 의 간이 차단

**중요한 차이:**
- Codex 는 `PermissionRequest` 가 별도 이벤트로 존재
- Codex 는 항상 *동시 실행* — 가드 정합성을 hook 간 순서로 보장 못 함
- Codex 의 `Stop` 은 *재개 메커니즘* 이라 의미가 반대
- Codex 의 PreToolUse 는 모든 도구를 가로채지 못함 → 완전한 enforcement 가 아님

---

## 8. Harness adapter 매핑 가이드

이 섹션은 향후 `standard/adapters/codex/` 의 `register.sh` / `translate-*.sh` 가 구체화될 때의 설계 지침.

### 8.1 standard hook → codex 이벤트 매핑

| Harness 표준 hook | Codex 이벤트 | 비고 |
|---|---|---|
| `session_start` | `SessionStart` | `source` 가 `startup` / `resume` / `clear` 중 하나. matcher 에 `startup\|resume` 권장 (clear 는 옵션). AGENTS.md 는 codex 가 native 인식하므로 별도 prefix 주입 불필요할 수 있음 — 검증 필요. |
| `user_prompt_submit` | `UserPromptSubmit` | matcher 없음 — 모든 prompt 에 발동 |
| `pre_tool_use` | `PreToolUse` | matcher 를 `Bash\|apply_patch\|Edit\|Write\|mcp__.*` 등으로. Claude 의 `Edit\|Write\|...` 매처와 다름 (codex 는 apply_patch 통합) |
| `permission_request` | `PermissionRequest` | Claude 엔 없는 이벤트 — codex 전용 분기 (`standard/hooks/permission_request/` 이미 존재) |
| `post_tool_use` | `PostToolUse` | matcher 동일하게 |
| `stop` | `Stop` | **의미 반대 주의** — codex 의 block 은 재개라서 `stop_validation` 매핑 시 주의 필요 |

### 8.2 envelope 변환 (translate scripts)

claude adapter 의 `translate-*.sh` 와 같은 패턴으로 작성. 주요 변환:

**codex → standard (stdin):**
```python
{
  "hook_type": "pre_tool_use",           # standard 이름으로 정규화
  "session_id": codex_input["session_id"],
  "project_root": codex_input["cwd"],
  "tool_name": codex_input["tool_name"],
  "tool_args": codex_input["tool_input"],
  # codex-only:
  "turn_id": codex_input.get("turn_id"),
  "tool_use_id": codex_input.get("tool_use_id"),
  "model": codex_input.get("model"),
}
```

**standard → codex (stdout):**
- standard hook 이 `{decision: "deny", reason: "..."}` 반환 시:
  - `PreToolUse` 인 경우 → `{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: "..."}}` 으로 변환
  - 또는 exit 2 + stderr 로 단순화
- `{decision: "allow"}` 인 경우 → exit 0, stdout 비움 (codex 기본 흐름)

### 8.3 등록 방식 결정

`register.sh` 는 두 등록 방식 중 **`hooks.json` 형식** 권장:
- 사용자의 `config.toml` 을 수정하지 않음 (코드 침습 최소)
- 별도 파일이라 unregister 가 단순 (파일 삭제 또는 entry 제거)
- claude adapter 의 `settings.local.json` 패턴과 1:1 대응

scope 선택:
- 프로젝트: `<repo>/.codex/hooks.json` — claude 의 `.claude/settings.local.json` 과 동격
- 글로벌 (옵트인 `--global`): `~/.codex/hooks.json`

### 8.4 활성화 전제

`register.sh` 가 수행해야 할 사전 검사·안내:

1. `[features] codex_hooks = true` 가 `~/.codex/config.toml` 에 있는지 확인. 없으면 추가하거나 사용자에게 안내.
2. 프로젝트 등록 시 `[projects."<cwd>"] trust_level = "trusted"` 가 있는지 확인. 없으면 안내 (untrusted 면 hook 이 안 동작).

### 8.5 PermissionRequest 의 별도 처리

Claude 엔 없는 이벤트. `standard/hooks/permission_request/` 가 이미 있으므로 — 그 hook 을 codex 의 `PermissionRequest` 에 등록하면 됨. claude adapter 에선 이 hook 이 호출될 일이 없음.

### 8.6 한계 명시

다음 항목은 codex 의 hook 모델 제약으로 **claude 와 같은 강도의 보장이 어려움**:

- `cognitive_guard` / `loop_detection` 의 도구 차단 — codex 가 가로채지 않는 도구 호출 (예: `WebSearch`) 에서는 발동 불가
- **동시 실행** 때문에 여러 hook 간 순서 의존 정책 (예: trace_log 가 먼저, 그 다음 cognitive_guard) 은 깨질 수 있음 — 정책끼리 독립적이도록 설계해야 함

이런 한계는 README / docs 의 "provider 별 지원 범위" 표에 명시할 필요.

---

## 부록 — 출처

- [Hooks – Codex (OpenAI Developers)](https://developers.openai.com/codex/hooks)
- [Configuration Reference – Codex (OpenAI Developers)](https://developers.openai.com/codex/config-reference)
- [hooks schema (GitHub)](https://github.com/openai/codex/tree/main/codex-rs/hooks/schema/generated)
