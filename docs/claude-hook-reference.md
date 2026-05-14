
[입문 §10](01-입문.md#10-hook-시스템) 의 hook 시스템이 참조하는 외부 레퍼런스. Claude Code 가 hook 시스템에서 **무엇을 기대하는지**, harness 가 그 안에서 **무엇을 어떻게 골랐는지** 의 detail.

> 공식 문서: [claude hook](https://code.claude.com/docs/ko/hooks)

## 목차

1. [#1. Hook 이벤트 종류](#1-hook-이벤트-종류)
2. [#2. Envelope — stdin·stdout 규약](#2-envelope--stdinstdout-규약)
3. [#3. Exit Code 프로토콜](#3-exit-code-프로토콜)
4. [#4. JSON 출력 — 풍부한 제어](#4-json-출력--풍부한-제어)
5. [#5. 왜 exit 2를 메인으로 골랐나](#5-왜-exit-2를-메인으로-골랐나)
6. [#6. 요약 매핑](#6-요약-매핑)

---

## 1. Hook 이벤트 종류

Claude Code가 발생시키는 주요 hook 이벤트:

| 이벤트 | 발동 시점 |
|---|---|
| `SessionStart` | 새 세션 시작 시 |
| `UserPromptSubmit` | 사용자가 prompt 제출 직후 |
| `PreToolUse` | LLM이 도구를 호출하기 *직전* (차단 가능) |
| `PostToolUse` | 도구 실행 *직후* (결과 후처리) |
| `Stop` | LLM이 응답을 끝내려는 시점 (block 가능) |

각 이벤트에 등록된 hook은 stdin으로 envelope JSON을 받고, 종료 코드·stdout으로 결과를 알림.

---

## 2. Envelope — stdin·stdout 규약

**stdin** (Claude → hook):

```json
{
  "session_id": "abc123",
  "transcript_path": "/path/to/transcript.jsonl",
  "cwd": "/path/to/project",
  "permission_mode": "default",
  "hook_event_name": "PreToolUse",
  "tool_name": "Edit",
  "tool_input": { "file_path": "...", "old_string": "...", "new_string": "..." }
}
```

이벤트마다 추가 필드가 다름 (예: `UserPromptSubmit`은 `prompt`, `Stop`은 `stop_hook_active` 등).

**stdout/exit code** (hook → Claude):

- exit code로 간단히 결정 전달
- 또는 stdout JSON으로 풍부한 제어
- stderr는 디버그 또는 *exit 2일 때 Claude로 전달*

---

## 3. Exit Code 프로토콜

Claude가 종료 코드별로 정한 반응:

| Exit | 의미 | Claude 반응 |
|---|---|---|
| `0` | 성공 | 그대로 진행 |
| **`2`** | **Blocking error** | **stderr를 Claude 시스템 메시지로 전달 → LLM이 그걸 읽고 자가수정** |
| 기타 non-zero (`1`, `3`, ...) | Non-blocking error | 로그만 남고 통과 |

**핵심**: `exit 2`만 Claude에게 *피드백 채널*이 있음. stderr에 `Required 미읽음: docs/foo.md` 한 줄만 쓰면 LLM이 그걸 보고 알아서 `Read("docs/foo.md")` 후 재시도.

---

## 4. JSON 출력 — 풍부한 제어

stdout에 JSON을 출력하면 더 정교한 제어 가능.

**PreToolUse 예시**:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Required Context not read"
  }
}
```

**Stop 예시**:
```json
{ "decision": "block", "reason": "Tests failing" }
```

**턴 전체 정지**:
```json
{ "continue": false, "stopReason": "Hard stop: SECURITY.md unread" }
```

→ `continue: false`는 단일 도구가 아니라 **현재 턴 자체를 종료**시킴. exit code로는 표현 불가능한 시그널.

---

## 5. 왜 exit 2를 메인으로 골랐나

Claude가 exit code와 JSON 두 메커니즘을 모두 지원하는데, harness는 **exit 2 우선**으로 설계.

### 이유 1 — Robustness

JSON 파싱은 escape 지옥. 특히 stderr에 들어갈 메시지에 따옴표·개행·백틱이 섞이면 매번 escape 처리. 개발 중 사례:

- 따옴표 escape 누락 → JSON parse 실패 → hook 무력화
- 개행 문자 처리 실패 → Claude가 메시지를 못 읽음

exit code는 **실패할 부분 자체가 없음**. `exit 2; echo "msg" >&2` 한 줄로 끝.

### 이유 2 — 언어 무관

Hook을 bash로 쓰는데 bash는 exit code가 native. JSON 직접 만들려면 `jq` 의존이 강하게 들어가고 메시지 escape를 jq로 처리해야 함.

### 이유 3 — 자가수정 채널이 정확히 의도와 일치

Required Context 미읽음 같은 **부드러운 거부**는 LLM이 알아서 회복하길 원함:

```
[hook이 deny]
  ↓ stderr: "Required 미읽음: docs/security.md"
[Claude가 stderr 읽음 → 시스템 메시지로 LLM에 전달]
  ↓ "이 도구 호출이 거부됐어. 이유: Required 미읽음: docs/security.md"
[LLM 자가수정]
  ↓ Read("docs/security.md")
  ↓ Edit(...) 재시도 → 이번엔 통과
```

이게 정확히 exit 2의 동작이고, 우리가 원하는 self_correct 흐름.

### 단, 턴 정지는 JSON 사용

진짜로 더 못 할 작업(예: SECURITY.md를 `hard_stop`으로 표시했는데 미읽음)은 자가수정도 막아야 함. 이건 exit code로 표현 안 되니 `{"continue": false}` JSON 사용.

---

## 6. 요약 매핑

```
[Claude의 규약]                          [Harness 매핑]
─────────────────────────                ──────────────
exit 0 + stdout 없음           →          allow
exit 2 + stderr 메시지         →          self_correct  (Required·Conditional Required·cognitive·loop 의 부드러운 거부)
JSON {"continue": false}       →          hard_stop     (severity 높은 거부)
JSON {permissionDecision}      →          (사용 안 함 — exit code로 충분)
```

**한 줄로**: Claude가 두 메커니즘을 다 줬는데, harness는 *간단하고 안정적인 exit 2를 1차*로, *턴 정지가 진짜 필요할 때만 JSON*으로 넘어감.
