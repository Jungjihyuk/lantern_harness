# Ralph Invokers

Provider-별 prompt → response 매개체.

## 인터페이스

```
<invoker>.sh <prompt_file> <response_file>
```

- 입력: `prompt_file` 의 텍스트가 prompt
- 출력: `response_file` 에 응답 텍스트 저장
- 종료 코드:
  - `0` — 성공
  - `1` — 사용자 abort
  - `99` — 이 invoker 미지원 (다른 invoker로 fallback 권장)

## 가용 Invokers

### manual.sh

사용자가 직접 paste·저장. 가장 안전·예측 가능. 우리 hook 시스템이 정상 작동 (claude session 내에서).

### claude.sh

`claude --print` 비대화 모드 시도. 환경별로 동작 다를 수 있음.

## 새 invoker 추가

`<name>.sh` 작성 → `~/.harness/know-how/ralph/invokers/<name>.sh`에 두면 자동 인식 가능 (단, `harness ralph start --invoker=<name>`).
