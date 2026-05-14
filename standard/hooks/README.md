# hooks plugin

표준 hook의 본 동작. **파일·이벤트 이름은 Claude Code 컨벤션과 정확히 매핑**.

## Hook 매핑 표

| 파일 | Claude 이벤트 | 도메인 역할 |
|---|---|---|
| `session_start.sh` | `SessionStart` | 컨텍스트 초기화 (AGENTS.md 주입, status JSON 초기화) |
| `user_prompt_submit.sh` | `UserPromptSubmit` | 가드레일 — 입력 필터 (placeholder) |
| `pre_tool_use.sh` | `PreToolUse` | 게이트 — Required·Conditional Required·loop·cognitive·path_blocklist 검사 |
| `post_tool_use.sh` | `PostToolUse` | 추적 — status·trace·timing 갱신 |
| `stop.sh` | `Stop` | 작업 검증 (`stop_validation.checks` 실행) |
| `post_commit.sh` | (git) | 진화 추적 — CHANGELOG 자동 갱신 |

## 입출력 envelope

stdin (provider 어댑터가 변환해 전달):
```json
{
  "hook_type": "pre_tool_use",
  "session_id": "abc123",
  "project_root": "/path/to/project",
  "tool_name": "Edit",
  "tool_args": {...}
}
```

stdout:
```json
{ "decision": "allow" | "deny", "reason": "...", "metadata": {...} }
```

## 우선순위

- `<project>/.harness/know-how/hooks/<name>.sh` 있음 → 통째 override (이 standard hook 무시).
- `<name>.sh` 없고 `<name>.d/*.sh` 있음 → 이 standard hook 실행 후 알파벳 순 chain.
- 둘 다 없음 → 이 standard hook만 실행.

## 실패 정책

- `session_start` — 사용자 안내 (세션 진행, prefix 누락 경고)
- `user_prompt_submit` — placeholder, 통과
- `pre_tool_use` — **차단** (보수적)
- `post_tool_use` — 통과 (로그)
- `stop` — 통과 (경고). `stop_validation.on_fail: block`이면 차단(exit 2)
