# AGENTS.md

Lantern Harness 위에서 작동 중. 이 prefix 는 매 응답 시 시야에 유지된다.

## 행동 원칙

1. **Required Context 먼저** — 변경 도구 (Edit / Write / NotebookEdit / Bash 등) 호출 전, `## Required Context` 의 모든 문서를 읽는다.
2. **Conditional Required 매칭 시 강제 읽기** — 편집 path 가 `## Conditional Required Context` 의 `when` 패턴과 매칭하면 그 항목의 문서 먼저 읽고 그 안의 지침을 따른다.
3. **인지 한계 안에서** — 한 번에 너무 큰 변경 X. 의도된 큰 변경은 prompt 에 `@harness allow-large` 마커로 한 번 통과.
4. **Sensitive path 안 만짐** — `.env`, `secrets/`, `.git/`, 키 / 인증 파일 등은 path_blocklist 가 차단.
5. **Hard Rules 우선** — `## Hard Rules` 블록의 강제 규칙은 위 일반 원칙보다 우선.

## 압축 정책

- 이 prefix 본문 + `## Hard Rules` = **압축 X** (세션 끝까지 시야).
- `## Required Context` / `## Conditional Required Context` / `## Suggested Context` = **path 메타만** prefix 에 박힘. 본문은 lazy — 필요 시점에 도구로 읽기.

## 컨텍스트 카탈로그 안내

아래 세 블록은 `compose.yaml` 의 `cognition.context.*` entries 에서 자동 합성된다:

- `## Required Context` — 작업 시작 전 *반드시* 읽을 문서
- `## Conditional Required Context` — 편집 path 가 `when` 패턴과 매칭하면 *강제 읽기 + 그 안의 행동 지침 따르기*
- `## Suggested Context` — 필요 시 자율 참고 (lazy, 안 봐도 됨)

본문은 prefix 에 안 들어감. *언제 어느 문서가 필요한지* 의 메타만.
