# AGENTS.md

Lantern Harness 위에서 작동 중. 이 prefix 는 매 응답 시 시야에 유지된다.

## 행동 원칙 (우선순위 순)

1. **Hard Rules** — `## Hard Rules` 의 강제 규칙은 *항상* 위. 다른 어떤 것보다 우선한다.
2. **Required Context** — 변경 도구 (Edit / Write / NotebookEdit / Bash 등) 호출 *전* 에 `## Required Context` 의 모든 문서를 읽는다.
3. **Conditional Required Context** — 지금 편집하려는 파일이 `## Conditional Required Context` 의 한 항목에 해당하면 (예: `db/database.py` 가 *DB 작업 시 따라야 할 규칙* 에 해당), 그 문서를 먼저 읽고 *그 안의 지침을 따라* 구현한다.
4. **Suggested Context** — 필요할 때 자율 참고. 안 봐도 무방.

## 자동 가드 (시스템이 도구 호출 직전 차단)

- **인지 한계 가드** — 한 번에 너무 큰 변경 (200줄 / 3 파일 초과 등) 시 차단. 의도된 큰 변경은 prompt 에 `@harness allow-large` 마커로 한 번 통과.
- **Sensitive Path** — `.env`, `secrets/`, `.git/`, 키 / 인증 파일 등 자동 차단. 우회 시도 X.

## 컨텍스트 무게

| 블록 | prefix 에 들어가는 것 | 의미 |
|---|---|---|
| **Hard Rules** | 본문 그대로 | 세션 내내 항상 시야에 유지 |
| **Required / Conditional Required / Suggested Context** | 파일 경로 + 라벨만 | 가볍게 — 실 본문은 필요 시점에 도구로 읽음 |

## 컨텍스트 카탈로그 안내

아래 세 블록은 `compose.yaml` 의 `cognition.context.*` 에서 자동 합성된다:

- `## Required Context` — 작업 시작 전 *반드시* 읽을 문서
- `## Conditional Required Context` — 작업 대상 파일이 매칭되면 *강제 읽기 + 그 안의 지침 따르기*
- `## Suggested Context` — 필요 시 자율 참고 (안 봐도 됨)
