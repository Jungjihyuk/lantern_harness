# adapters

Provider별 어댑터. 우리 표준 hook/AGENTS.md를 각 provider 시스템에 매핑.

## 두 책임

1. **Register**: `harness link <provider>` 시 provider hook 시스템에 표준 hook을 자동 등록.
2. **Translate**: provider hook 입력 ↔ 표준 envelope 변환 (실시간).

## 도구 중립 invariant

- 표준 envelope·표준 hook은 어댑터 무관하게 안정.
- 새 provider 어댑터 추가 = `register.sh` + `unregister.sh` + `translate-*.sh` 작성만.

## AGENTS.md 주입 패턴

- **Claude**: `runtime/AGENTS.resolved.md` → 프로젝트의 `CLAUDE.md`로 symlink (claude native auto-load).
- **Codex**: `runtime/AGENTS.resolved.md` → 프로젝트 루트의 `AGENTS.md`로 symlink (codex native).
- **다른 도구**: 도구별 native 메커니즘에 맞춰.
