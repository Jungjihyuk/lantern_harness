# ralph

무인 self-loop 워크플로 artifact (`mechanism: workflows`, `domain: state`, `role: workflow_step`). `compose.yaml` 의 `state.workflows` entry 로 활성.

## compose schema

```yaml
state:
  workflows:
    - id: ralph
      task: ./TASK.md         # 작업 명세 (필수)
      max_iterations: 20      # 최대 반복
      verify:
        commands:             # 모두 exit 0 → loop 종료 (성공)
          - "pytest -x"
          - "tsc --noEmit"
      stuck_threshold: 3      # (선택) 같은 path 연속 수정 N회
      on_stuck: ask_human     # (선택) ask_human | abort
```

## 동작

1. invoker 로 agent 호출 (task prompt 기반)
2. `verify.commands` 순차 실행
3. 모두 통과 → loop 종료 (성공)
4. 하나라도 실패 → 다음 iteration (직전 출력을 prompt 에 포함)
5. `max_iterations` 도달 → 종료 (실패)

`verify.commands` 미지정 시 verify 단계 skip (사용자가 invoker 호출만 반복).

## Stuck detection

같은 path 연속 수정 카운터. `stuck_threshold` 초과 시 `on_stuck` 정책 적용.

## Cognitive guard 와의 관계

ralph 활성 (state.workflows 에 등록) 시 `pre_tool_use` 의 `loop_detection` 가드가 자동 활성 — 같은 path 를 N회 연속 수정하려 하면 `self_correct` 응답.
