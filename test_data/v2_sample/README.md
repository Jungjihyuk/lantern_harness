# sample — `harness validate` e2e 검증용

architecture schema (`docs/architecture.md`) 가 실제로 작동하는지
검증하기 위한 최소 샘플 자산.

## 구조

```
test_data/v2_sample/
├── standard/
│   ├── roles.yaml                              # 도메인별 허용 role enum
│   ├── instructions/agents_md/
│   │   ├── manifest.yaml
│   │   └── AGENTS.md                            # prefix 주입용 텍스트
│   └── hooks/pre_tool_use/
│       ├── manifest.yaml
│       └── handler.sh                           # (검증 시연용 placeholder)
└── .harness/
    └── compose.yaml                             # schema 활용 예
```

샘플 내용:
- 1 prefix entry (`agents_md`) → cognition.prefix 에 등록
- 1 hook (`pre_tool_use`) → guard.hooks 에 3 entries + observe.hooks 1 entry (N:N)
- guard.policies (cognitive_guard, loop_detection) 포함

## 사용

```bash
cd test_data/v2_sample

# 정상 검증
../../bin/cmd/validate.sh --standard ./standard --know-how ./.harness/know-how
# → ✓ compose.yaml valid — 5 entries (cognition: 1, guard: 3, observe: 1)

# 에러 검증 (잘못된 role 등을 compose 에 넣고 시도)
```

## 목적

- validate CLI 가 정말 동작하는지 확인
- 향후 schema 변경 시 회귀 테스트 reference
- 새 contributor 가 schema 를 빠르게 이해할 수 있는 살아있는 예시

## 주의

- `handler.sh` 는 실제 검사 로직 X. 검증 시연용 placeholder.
- 실제 production 자산이 아니므로 `harness link` / `harness install` 대상이 아님.
- standard/know-how 분리 정책 (§8.6.3) 검증을 위해 별도 충돌 케이스도 작성 가능.
