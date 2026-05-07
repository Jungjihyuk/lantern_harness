# ~/.harness/standard

도구·도메인 중립 standard 자원이 평평하게 모이는 곳. 누구나 가져다 자기 프로젝트에 layering으로 적용.

## 한눈에 이해하기

`standard/`(공통 기본값)와 프로젝트별 `know-how/`(개인 노하우)는 **부모-자식 관계**.
같은 path를 know-how가 두면 가려지고(override), `<name>.d/*.sh`로 두면 뒤에 추가 실행(chain).

## 구조

- `AGENTS.md` — 표준 md (prefix 주입). 4 블록 + Hard Rules.
- `hooks/` — 표준 hook plugin (session_start · user_prompt_submit · pre_tool_use · post_tool_use · stop · post_commit). Claude Code 이벤트와 1:1 매핑.
- `ralph/` — 무인 루프 러너 plugin.
- `adapters/{claude,codex,omo}/` — provider별 어댑터 (hook system 매핑).

## 표준 md 자격 기준

새 표준 md 추가 시 4 기준 모두 통과해야 함:
1. 항상 적용되어야 하는가
2. 압축되면 손해가 큰가
3. 짧게 표현 가능한가
4. 프로젝트 무관 보편적인가

## Layering 우선순위

프로젝트의 `know-how/`가 `standard/`보다 우선. 같은 path = override, `<name>.d/*.sh` = chain (super 후 추가).
