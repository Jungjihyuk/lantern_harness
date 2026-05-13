# adapters

Provider별 어댑터 (외부 결합 layer). 표준 hook / AGENTS.md 를 각 provider 시스템에 매핑.

> 다른 메커니즘과의 차이: instructions/hooks/workflows 등이 *agent 내부 행동 명세* 라면, adapters 는 *외부 시스템과의 결합 표면* (AIMA 의 actuator 쪽). percept 쪽은 `cognition.context` 에서 담당.

## 폴더 구조

- `claude/`, `codex/` — provider artifact (각 폴더에 `manifest.yaml + driver.py + register.sh + translate-*.sh`)
- **엔진 코드는 별도 위치**: `lib/adapters/` 에 `base.py / registry.py / _mutation.py / list.py / show.py / enable.py / disable.py` — `harness list / show / enable / disable` 가 호출.

## 두 책임 (provider artifact)

1. **Register**: `harness link <provider>` 시 provider hook 시스템에 표준 hook을 자동 등록.
2. **Translate**: provider hook 입력 ↔ 표준 envelope 변환 (실시간).

## 도구 중립 invariant

- 표준 envelope·표준 hook은 어댑터 무관하게 안정.
- 새 provider 어댑터 추가 = `manifest.yaml` + `driver.py` + `register.sh` + `unregister.sh` + `translate-*.sh` 작성.

## AGENTS.md 주입 패턴

- **Claude**: `runtime/AGENTS.resolved.md` → 프로젝트의 `CLAUDE.md`로 symlink (claude native auto-load).
- **Codex**: `runtime/AGENTS.resolved.md` → 프로젝트 루트의 `AGENTS.md`로 symlink (codex native).
- **다른 도구**: 도구별 native 메커니즘에 맞춰.
