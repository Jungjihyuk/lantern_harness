# ralph plugin

무인 루프 러너. `compose.yaml`의 `mode: ralph`일 때 활성.

## 두 모드 (자동 선택)

- **모드 A 단일 task**: `ralph.task` 적힘 → `know-how/ralph-task.md` 한 파일.
- **모드 B stage chain**: `ralph.stages` 적힘 → `know-how/ralph-stages.yaml`.

## 검증 (자동 선택)

- **간단 모드**: `ralph.verify` 명세 없음 → `know-how/ralph/verify.sh` 단일 스크립트.
- **계층 모드**: `ralph.verify` 리스트 → 위에서 아래로 모두 통과해야 done.

## Stuck detection

같은 path 연속 수정 카운터. `stuck_threshold` 초과 → `on_stuck` 정책 (`ask_human` | `abort`).

## Cognitive guard

ralph 모드에서도 active. `ask_human`은 자동 `abort` fallback.
