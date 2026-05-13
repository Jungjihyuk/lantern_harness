# traces/

agent 실행 중 발생한 **raw 관측 데이터** (input/output 텍스트, 토큰 수, 성공/오류 메시지 등) 의 스키마/수집 정의 모음.

- 각 trace: `<id>/manifest.yaml + 스키마/수집 코드` 패턴.
- 주 도메인: `observe` (compose.yaml 의 `observe.traces` entry).
- `evals/` 와의 경계: **traces = raw 데이터**, **evals = 그것을 판정한 verdict**.

현재 비어있음. 누적되는 trace 정의가 검증되면 여기 모임.
